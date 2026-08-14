---
name: clash-ipfly
description: Configure and verify Clash Verge Rev so local port 7898 always uses an IPFly static residential SOCKS5 exit, and configure the zsh claude command to use that port automatically. Read IPFly credentials and the expected fixed IP from IP列表.xlsx. Use when the user asks to set up, restore, diagnose, or verify Clash 7898, IPFly residential static IP, or Claude CLI fixed egress after a subscription change.
---

# Clash 7898 to IPFly

Build exactly this path:

```text
claude -> HTTP_PROXY/HTTPS_PROXY 127.0.0.1:7898
       -> Clash listener 7898
       -> IPFly static SOCKS5 through the current Clash Proxies group
       -> workbook residential IP
```

## Run

1. Keep `assets/IP列表.xlsx` local and ignored by Git. Never print its username or password.
2. Preview the selected `Status=Normal` account:

   ```bash
   python3 scripts/configure_ipfly.py
   ```

3. Install the persistent Clash global script and the zsh `claude()` wrapper:

   ```bash
   python3 scripts/configure_ipfly.py --apply
   ```

   Pass `--workbook <path>` when the local asset is absent. Pass `--upstream-group <name>` only when the subscription has no `Proxies` group.

4. Reactivate the current subscription in Clash Verge so `profiles/Script.js` regenerates the runtime config. Do not claim success before this step.
5. Open a new zsh session or run `source ~/.zshrc`.
6. Verify:

   ```bash
   python3 scripts/configure_ipfly.py --verify
   zsh -lic 'type claude'
   ```

7. Finish only when all IP checks equal the workbook IP and `claude` resolves to the wrapper that sets both proxy variables to `127.0.0.1:7898`.

## Guardrails

- Back up `profiles/Script.js`, `clash-verge.yaml`, and `.zshrc` before changing them.
- Persist in `profiles/Script.js`; never rely only on generated `clash-verge.yaml`, which subscription updates overwrite.
- Refuse to overwrite unrelated existing `main()` or `claude()` functions without explicit approval.
- Keep the dedicated listener bound to `127.0.0.1`, not LAN interfaces.
- If 7898 works intermittently, test another existing upstream group or node through the complete path. Read `references/Clash-Verge-IPFly-静态出口配置指南.md` only for that troubleshooting path.

## Files

- `scripts/configure_ipfly.py` -> read the workbook, install the Clash script and Claude wrapper, back up files, and verify the exit.
- `assets/IP列表.xlsx` -> local IPFly account and expected residential IP; intentionally ignored by Git.
- `references/Clash-Verge-IPFly-静态出口配置指南.md` -> detailed fallback troubleshooting.
