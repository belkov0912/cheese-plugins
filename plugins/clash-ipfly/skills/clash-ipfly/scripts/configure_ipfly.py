#!/usr/bin/env python3
"""Persist and verify an IPFly static SOCKS5 egress in Clash Verge Rev."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = SKILL_DIR / "assets" / "IP列表.xlsx"
DEFAULT_CLASH_DIR = (
    Path.home()
    / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"
)
MANAGED_BEGIN = "// BEGIN clash-ipfly managed configuration"
MANAGED_END = "// END clash-ipfly managed configuration"
SHELL_BEGIN = "# BEGIN clash-ipfly managed configuration"
SHELL_END = "# END clash-ipfly managed configuration"


def cell_text(cell: ET.Element, shared: list[str]) -> str:
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{namespace}t"))
    value = cell.find(f"{namespace}v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s" and raw:
        return shared[int(raw)]
    return raw


def read_workbook(path: Path) -> list[tuple[int, dict[str, str]]]:
    if not path.is_file():
        raise RuntimeError(f"IPFly workbook not found: {path}")

    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(node.text or "" for node in item.iter(f"{namespace}t"))
                for item in root.findall(f"{namespace}si")
            ]

        sheets = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
        )
        if not sheets:
            raise RuntimeError("workbook has no worksheets")
        root = ET.fromstring(archive.read(sheets[0]))

    # xlsx omits fully empty rows, so keep each row's own Excel number (@r)
    # instead of inferring it from the position in the sheet.
    raw_rows: list[tuple[int, dict[str, str]]] = []
    for row in root.iter(f"{namespace}row"):
        reference = row.attrib.get("r", "")
        row_number = int(reference) if reference.isdigit() else len(raw_rows) + 1
        values: dict[str, str] = {}
        for cell in row.findall(f"{namespace}c"):
            reference = cell.attrib.get("r", "")
            column = re.sub(r"\d", "", reference)
            values[column] = cell_text(cell, shared).strip()
        raw_rows.append((row_number, values))

    if len(raw_rows) < 2:
        raise RuntimeError("workbook must contain a header and at least one data row")
    headers = raw_rows[0][1]
    return [
        (
            number,
            {header: raw.get(column, "") for column, header in headers.items() if header},
        )
        for number, raw in raw_rows[1:]
    ]


def select_account(
    rows: list[tuple[int, dict[str, str]]], row_number: int | None
) -> dict[str, str]:
    if row_number is not None:
        matched = [values for number, values in rows if number == row_number]
        if not matched:
            available = ", ".join(str(number) for number, _ in rows)
            raise RuntimeError(
                f"Excel row {row_number} holds no data (data rows: {available})"
            )
        selected = matched[0]
    else:
        normal = [
            values
            for _, values in rows
            if values.get("Status", "").casefold() == "normal"
        ]
        if len(normal) != 1:
            raise RuntimeError(
                f"expected exactly one Status=Normal row, found {len(normal)}; "
                "pass --row-number explicitly"
            )
        selected = normal[0]

    required = ["Host", "IP", "Ports", "user", "password"]
    missing = [key for key in required if not selected.get(key)]
    if missing:
        raise RuntimeError(f"selected row is missing fields: {', '.join(missing)}")
    return selected


def normalize_port(raw: str) -> int:
    try:
        port = int(float(raw))
    except ValueError as exc:
        raise RuntimeError(f"invalid IPFly port: {raw!r}") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError(f"IPFly port is outside 1..65535: {port}")
    return port


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_script(
    account: dict[str, str], listener_port: int, upstream_group: str
) -> str:
    host = js_string(account["Host"])
    username = js_string(account["user"])
    password = js_string(account["password"])
    upstream = js_string(upstream_group)
    port = normalize_port(account["Ports"])
    return f'''{MANAGED_BEGIN}
function main(config, profileName) {{
  const staticProxy = "Claude静态出口";
  const listenerName = "claude-cli";
  const requestedUpstream = {upstream};
  const groups = Array.isArray(config["proxy-groups"])
    ? config["proxy-groups"]
    : [];
  const upstream = groups.find(
    (group) => group && group.name === requestedUpstream,
  );

  if (!upstream) {{
    console.log(`[IPFly] upstream group not found: ${{requestedUpstream}}`);
    return config;
  }}

  config.proxies = (config.proxies || []).filter(
    (proxy) => proxy && proxy.name !== staticProxy,
  );
  config.proxies.push({{
    name: staticProxy,
    type: "socks5",
    server: {host},
    port: {port},
    username: {username},
    password: {password},
    udp: false,
    tfo: false,
    "ip-version": "ipv4-prefer",
    "dialer-proxy": upstream.name,
  }});

  config.listeners = (config.listeners || []).filter(
    (listener) =>
      listener && listener.name !== listenerName && listener.port !== {listener_port},
  );
  config.listeners.push({{
    name: listenerName,
    type: "mixed",
    listen: "127.0.0.1",
    port: {listener_port},
    proxy: staticProxy,
  }});

  return config;
}}
{MANAGED_END}
'''


def is_replaceable_script(text: str) -> bool:
    empty_stub = re.fullmatch(
        r"\s*(?://[^\n]*\n\s*)*function\s+main\(config,\s*profileName\)\s*"
        r"\{\s*return\s+config;?\s*\}\s*",
        text,
    )
    legacy = (
        text.count("function main(") == 1
        and '"Claude静态出口"' in text
        and '"claude-cli"' in text
        and '"dialer-proxy"' in text
        and "port: 7898" in text
    )
    return bool(empty_stub or legacy or not text.strip())


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def has_proxy_group(config_text: str, group_name: str) -> bool:
    """Report whether group_name is a proxy *group* at any indentation level.

    Scanning is confined to the `proxy-groups:` block so a proxy that happens to
    share the group name cannot satisfy the check (the installed script matches
    on proxy-groups only, and would bail out at runtime).
    """
    quoted = re.escape(group_name)
    entry = re.compile(
        rf"""(?:^|[-\[{{,]\s*)name:\s*(?:"{quoted}"|'{quoted}'|{quoted})\s*(?=$|[,}}\]])"""
    )
    block_indent: int | None = None
    for line in config_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if block_indent is not None:
            # Sequence items may sit at the key's own indentation.
            if indent > block_indent or stripped.startswith("-"):
                if entry.search(stripped):
                    return True
                continue
            block_indent = None
        if stripped.startswith("proxy-groups:"):
            block_indent = indent
            if entry.search(stripped[len("proxy-groups:") :].strip()):
                return True
    return False


def backup_copy(source: Path, target: Path) -> None:
    """Copy into the backup dir; the saved config can hold plaintext credentials."""
    shutil.copy2(source, target)
    os.chmod(target, 0o600)


def render_shell_wrapper(listener_port: int) -> str:
    return f'''{SHELL_BEGIN}
claude() {{
  HTTPS_PROXY=http://127.0.0.1:{listener_port} \\
  HTTP_PROXY=http://127.0.0.1:{listener_port} \\
  NO_PROXY=localhost,127.0.0.1,.zhihu.com,.in.zhihu.com,10.0.0.0/8 \\
  command claude "$@"
}}
{SHELL_END}'''


def update_shell_config(text: str, listener_port: int) -> tuple[str, bool]:
    block = render_shell_wrapper(listener_port)
    if SHELL_BEGIN in text and SHELL_END in text:
        start = text.index(SHELL_BEGIN)
        end = text.index(SHELL_END) + len(SHELL_END)
        return text[:start] + block + text[end:], True

    function = re.search(r"(?ms)^claude\(\)\s*\{.*?^\}", text)
    if function:
        proxy = f"http://127.0.0.1:{listener_port}"
        body = function.group(0)
        if f"HTTP_PROXY={proxy}" in body and f"HTTPS_PROXY={proxy}" in body:
            return text, False
        raise RuntimeError(
            "~/.zshrc already defines another claude() function; refusing to overwrite it"
        )

    separator = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + separator + block + "\n", True


def install_script(
    clash_dir: Path,
    script: str,
    upstream_group: str,
    listener_port: int,
    zshrc_path: Path,
    force_replace: bool,
) -> tuple[Path, Path, bool]:
    script_path = clash_dir / "profiles/Script.js"
    config_path = clash_dir / "clash-verge.yaml"
    if not config_path.is_file():
        raise RuntimeError(f"generated Clash config not found: {config_path}")
    config_text = config_path.read_text(encoding="utf-8")
    if not has_proxy_group(config_text, upstream_group):
        raise RuntimeError(
            f"upstream group {upstream_group!r} is not present in the current subscription"
        )

    existing = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
    if MANAGED_BEGIN in existing and MANAGED_END in existing:
        start = existing.index(MANAGED_BEGIN)
        end = existing.index(MANAGED_END) + len(MANAGED_END)
        updated = existing[:start] + script.rstrip() + existing[end:]
    elif is_replaceable_script(existing) or force_replace:
        updated = script
    else:
        raise RuntimeError(
            "global Script.js contains unrelated custom logic; refusing to overwrite it. "
            "Merge manually or rerun with --force-replace-script after reviewing the backup."
        )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = clash_dir / f"ipfly-backup-{timestamp}"
    attempt = 1
    while backup_dir.exists():
        attempt += 1
        backup_dir = clash_dir / f"ipfly-backup-{timestamp}-{attempt}"
    backup_dir.mkdir(parents=True, mode=0o700)
    if script_path.exists():
        backup_copy(script_path, backup_dir / "Script.js")
    backup_copy(config_path, backup_dir / "clash-verge.yaml")
    shell_text = zshrc_path.read_text(encoding="utf-8") if zshrc_path.exists() else ""
    updated_shell, shell_changed = update_shell_config(shell_text, listener_port)
    if shell_changed and zshrc_path.exists():
        backup_copy(zshrc_path, backup_dir / ".zshrc")
    atomic_write(script_path, updated.rstrip() + "\n")
    if shell_changed:
        atomic_write(zshrc_path, updated_shell)
    return script_path, backup_dir, shell_changed


def curl_exit_ip(proxy_url: str, url: str) -> tuple[int, str]:
    command = [
        "curl",
        "--ipv4",
        "--silent",
        "--show-error",
        "--location",
        "--fail",
        "--connect-timeout",
        "5",
        "--max-time",
        "20",
        "--retry",
        "2",
        "--retry-delay",
        "1",
        "--retry-all-errors",
        "--proxy",
        proxy_url,
        url,
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return result.returncode, result.stderr.strip()
    match = re.search(r"^ip=([^\r\n]+)$", result.stdout, re.M)
    if match:
        return 0, match.group(1).strip()
    plain = result.stdout.strip()
    return (0, plain) if re.fullmatch(r"[0-9a-fA-F:.]+", plain) else (2, "no IP in response")


def verify(listener_port: int, expected_ip: str) -> bool:
    proxy_url = f"http://127.0.0.1:{listener_port}"
    targets = [
        ("IP lookup", "https://api.ipify.org"),
        ("Cloudflare", "https://1.1.1.1/cdn-cgi/trace"),
        ("Claude Web", "https://claude.ai/cdn-cgi/trace"),
        ("Anthropic API", "https://api.anthropic.com/cdn-cgi/trace"),
    ]
    success = True
    for label, url in targets:
        code, output = curl_exit_ip(proxy_url, url)
        if code == 0 and output == expected_ip:
            print(f"{label:14} -> {output}")
        else:
            success = False
            safe_output = output if code == 0 else f"request failed (curl {code})"
            print(f"{label:14} -> {safe_output}")
    print(f"result         -> {'consistent' if success else 'failed'}")
    return success


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--row-number", type=int)
    parser.add_argument("--clash-dir", type=Path, default=DEFAULT_CLASH_DIR)
    parser.add_argument("--listener-port", type=int, default=7898)
    parser.add_argument("--upstream-group", default="Proxies")
    parser.add_argument("--zshrc", type=Path, default=Path.home() / ".zshrc")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--force-replace-script", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rows = read_workbook(args.workbook.expanduser().resolve())
        account = select_account(rows, args.row_number)
        script = render_script(account, args.listener_port, args.upstream_group)
        print(f"account        -> {account['Host']}:{normalize_port(account['Ports'])}")
        print(f"expected IP    -> {account['IP']}")
        print(f"credentials    -> loaded (redacted)")
        print(f"upstream group -> {args.upstream_group}")

        if args.apply:
            script_path, backup_dir, shell_changed = install_script(
                args.clash_dir.expanduser().resolve(),
                script,
                args.upstream_group,
                args.listener_port,
                args.zshrc.expanduser().resolve(),
                args.force_replace_script,
            )
            print(f"installed      -> {script_path}")
            print(f"claude wrapper -> {'installed' if shell_changed else 'already configured'}")
            print(f"backup         -> {backup_dir}")
            print("next           -> reactivate the current subscription in Clash Verge")
        else:
            print("mode           -> dry-run (pass --apply to install)")

        if args.verify:
            return 0 if verify(args.listener_port, account["IP"]) else 1
        return 0
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
