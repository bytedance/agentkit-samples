# Credential integration

Credential intents use the same `byted-util-ark-cua` CLI. The signed Agent installer, source readiness checks, browser sync orchestration, and non-browser resource sync orchestration are shipped directly under this Skill's `scripts/` directory. There is no runtime download, cache, installation, or release dependency on another Skill.

The CLI first checks the selected AgentPlan `/skill/manifest` and exact `cua_credential_*` tools. Only after the production Gateway advertises the capability may it install or update the signed Credential Agent and prepare the source browser. The Gateway bootstrap profile binds every operation to the production environment, service origins, and policy authority.

The trust path is:

`AgentPlan credential handle -> existing Skill Gateway tools -> caller-owned exact desktop -> signed target Credential Agent`

The local AgentPlan key remains inside the non-serializable auth handle. Pairing codes move only through the one-time encrypted relay between the source and target Agents. Secret values remain inside Credential Agent subprocesses; the CLI returns bounded status and identifiers only.

## Workflow

1. Run `credentials status [--desktop-id <id>]`. This is read-only. If the Gateway reports `TARGET_CAPABILITY_UNAVAILABLE`, stop; do not install/update the Agent and do not fall back to a model task.
2. Run `credentials setup [--desktop-id <id>]` only when setup is requested or the exact target is not ready. Add `--skip-browser` for non-browser resources.
3. Initial Chrome extension installation is deliberately one manual, cross-platform step. The Skill verifies and prepares the signed extension, requests `chrome://extensions/` and the exact directory to open, then returns `SOURCE_BROWSER_USER_ACTION_REQUIRED`. Ask the user only to enable developer mode, click Load unpacked, and select that exact directory. Do not use macOS Accessibility automation, edit the Chrome Profile, copy cookies, or broaden the requested site. Rerun the same request after the fixed extension connects; existing connected extensions may update themselves without UI automation.
4. Run one exact sync command:

   ```bash
   python3 scripts/cua.py credentials sync browser --desktop-id <id> <site>...
   python3 scripts/cua.py credentials sync env --desktop-id <id> <name>...
   python3 scripts/cua.py credentials sync secret --desktop-id <id> <name>...
   python3 scripts/cua.py credentials sync credential-set --desktop-id <id> --type <type> --name <name>
   python3 scripts/cua.py credentials sync file --desktop-id <id> --profile <profile>
   ```

5. Preserve the returned Job identity and let the authoritative workflow reach its terminal state. Do not start a second sync because a client-side wait ended.

Normal CUA browsing and task delegation never imply credential synchronization. Do not invent `--all`, discover extra resources, or broaden the user's requested scope.

## Browser permission boundary

The browser extension's required `host_permissions: ["https://*/*"]` is a browser capability, not business authorization. The target still requires a Vault-signed Policy for an exact HTTPS Origin, validates its digest/version and Cookie/Storage/validation scope, and checks `chrome.permissions.contains()` for that exact Origin before every task.

Do not call `chrome.permissions.request()` or `remove()`, open Options, or use `open-permissions` as setup. The internal `browser-authorize-begin/watch` Adapter actions are compatibility-only read-only observations; the normal `sync-cua.py` path does not call them. If Chrome withholds Site access, keep the same Job in `waiting_permission`, report `HOST_PERMISSION_REQUIRED`, and wait for the user to restore Site access. Never bypass the check or create a per-origin fallback.

## Reset

```bash
python3 scripts/cua.py credentials reset --desktop-id <id> [--device-id <exact-id>]
```

Reset is resumable and ordered: centrally revoke the exact Device ID first, require a confirmed `revoked` response, and only then reset the exact target. If central revocation is not confirmed, do not delete local state or reset the target.
