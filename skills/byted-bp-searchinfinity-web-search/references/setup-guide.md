# BytePlus Web Search — Activation & Configuration

**Out-of-the-box flow**: register → activate → grab a Key → **paste the Key into the chat** (no config editing) → done.

> Use only the official BytePlus console and docs:
>
> - Activate: https://console.byteplus.com/search-infinity/web-search
> - Key management: https://console.byteplus.com/search-infinity/api-key
> - API docs: https://docs.byteplus.com/en/docs/searchinfinity/Searchinfinity_API_Reference

---

## 1. Register an account

Visit BytePlus, register and sign in (first-time use requires basic verification such as email confirmation).

## 2. Activate the web search service

Open the [Searchinfinity Web Search console](https://console.byteplus.com/search-infinity/web-search) → click **Activate**.
Once activated, you can create credentials on the API Key page.

## 3. Create an API Key (recommended)

[API Key management](https://console.byteplus.com/search-infinity/api-key) → **Create API Key** → copy and store it safely.

> ⚠️ **Authentication Method: APIKey only** — this skill only accepts API Keys issued by the **Searchinfinity console**; Keys from other sources will not work.
>
> The script strictly follows the official docs:
> - **Interface URL**: `https://torchlight.byteintlapi.com/search_api/web_search` (POST + `application/json`)
> - **Auth header**: `Authorization: Bearer <ApiKey>`. **Do not** use `X-Api-Key` / `Apikey:`, and **do not** use AK/SK signing (HMAC-SHA256).

## 4. Hand the Key to your AI application

Pick any one method (listed in priority order):

- **[Recommended / simplest]** Paste the Key directly into the chat with your AI application — the Agent binds it automatically, **no config editing required**.
- **Environment variable**: `export I18N_WEB_SEARCH_API_KEY="your_key"` (add to `~/.bashrc` / `~/.zshrc` to persist).
- **Local `.env`**: create `.env` in the skill root with:
  ```
  I18N_WEB_SEARCH_API_KEY=your_key
  ```
- **User-level `.env`**: place it at `~/.byteplus/.env` — the script auto-loads from there.
- **Pass at runtime**: invoke the script with `--api-key "your_key"` or `--prompt-api-key` (interactive, no echo).

## 5. Verify the install

```bash
cd byted-bp-searchinfinity-web-search
python3 scripts/web_search.py "BytePlus web search"
```

A healthy run prints `ResultCount / TimeCost` followed by entries like `[index] title / source / URL / summary`.

For recent content, add a time filter:

```bash
python3 scripts/web_search.py "latest AI industry news" --time-range OneWeek
```

---

## Common issues

| Symptom | Resolution |
|---------|------------|
| `invalid_api_key` / `700901` Invalid ApiKey | Key doesn't match the service. Confirm it was created at [API Key management](https://console.byteplus.com/search-infinity/api-key) and the service is activated; re-copy (watch for leading/trailing whitespace) and paste it again. |
| `700429` QPS exceeded | Default 5 QPS. Back off with 1s → 2s → 4s; keep concurrency per Key ≤ 5. |
| `10403` quota exhausted | Check / top up at the [activation page](https://console.byteplus.com/search-infinity/web-search). |
| Parameter validation failed | TimeRange supports only `OneDay` / `OneWeek` / `OneMonth` / `OneYear` or `YYYY-MM-DD..YYYY-MM-DD`; Count must be in 1–20; Query must be ≤ 400 chars / ≤ 50 words. |
| Configured but still "credential not found" | Confirm the env var is `I18N_WEB_SEARCH_API_KEY` (case-sensitive); confirm the `.env` is at the skill root or `~/.byteplus/.env`. |
| Want to swap the Key | Just paste the new Key into the chat; the script picks up the latest value. |

---

## Security notes

- The API Key is equivalent to account access — **never hardcode it into repos, public logs, or screenshots**.
- In production, inject the Key via a secret manager (KMS / Vault / Secrets Manager, etc.).
- If you suspect a leak, immediately delete the old Key on [API Key management](https://console.byteplus.com/search-infinity/api-key) and create a new one.
