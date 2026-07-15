#!/usr/bin/env python3
"""Locate read-only Obsidian daily-note context for trade review."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import date
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Locate top-level 02-Daily notes without modifying the vault."
    )
    parser.add_argument("--trade-date", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--vault",
        default=os.environ.get("TRADE_REVIEW_OBSIDIAN_VAULT"),
        help="Vault name; defaults to TRADE_REVIEW_OBSIDIAN_VAULT or active vault.",
    )
    parser.add_argument("--folder", default="02-Daily")
    return parser.parse_args()


def run_obsidian(vault: str | None, *args: str) -> str:
    command = ["obsidian"]
    if vault:
        command.append(f"vault={vault}")
    command.extend(args)
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def relation(note_date: date, trade_date: date) -> str:
    if note_date < trade_date:
        return "before_trade_date"
    if note_date == trade_date:
        return "same_trade_date"
    return "after_trade_date"


def note_payload(note_date: date, path: str, trade_date: date) -> dict[str, str]:
    return {
        "path": path,
        "date": note_date.isoformat(),
        "relation_to_trade_date": relation(note_date, trade_date),
    }


def main() -> None:
    args = parse_args()
    folder = args.folder.rstrip("/")
    pattern = re.compile(
        rf"^{re.escape(folder)}/([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})[.]md$"
    )

    try:
        output = run_obsidian(args.vault, "files", f"folder={folder}", "ext=md")
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        emit(
            {
                "status": "unavailable",
                "vault": args.vault or "active vault",
                "folder": folder,
                "trade_date": args.trade_date.isoformat(),
                "error": detail.strip(),
            }
        )
        return

    notes: list[tuple[date, str]] = []
    for raw_path in output.splitlines():
        path = raw_path.strip()
        match = pattern.fullmatch(path)
        if not match:
            continue
        try:
            notes.append((date.fromisoformat(match.group(1)), path))
        except ValueError:
            continue

    if not notes:
        emit(
            {
                "status": "no_daily_notes",
                "vault": args.vault or "active vault",
                "folder": folder,
                "trade_date": args.trade_date.isoformat(),
                "latest_note": None,
                "score_eligible_note": None,
                "same_day_note": None,
            }
        )
        return

    notes.sort()
    latest_date, latest_path = notes[-1]
    eligible = [item for item in notes if item[0] < args.trade_date]
    same_day = [item for item in notes if item[0] == args.trade_date]

    emit(
        {
            "status": "ready",
            "vault": args.vault or "active vault",
            "folder": folder,
            "trade_date": args.trade_date.isoformat(),
            "latest_note": note_payload(latest_date, latest_path, args.trade_date),
            "score_eligible_note": (
                note_payload(eligible[-1][0], eligible[-1][1], args.trade_date)
                if eligible
                else None
            ),
            "same_day_note": (
                note_payload(same_day[-1][0], same_day[-1][1], args.trade_date)
                if same_day
                else None
            ),
        }
    )


if __name__ == "__main__":
    main()
