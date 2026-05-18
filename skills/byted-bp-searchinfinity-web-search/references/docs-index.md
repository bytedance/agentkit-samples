# BytePlus Web Search — Docs Index

Activation, credential setup, API troubleshooting, and configuration notes for this skill cite only the three official URLs below — no other external links — to avoid confusing credential sources. Final search answers should cite the source URLs returned by the API when they support the answer.

## Official links

| Purpose | URL |
|---------|-----|
| Service activation | https://console.byteplus.com/search-infinity/web-search |
| API Key management | https://console.byteplus.com/search-infinity/api-key |
| API reference | https://docs.byteplus.com/en/docs/searchinfinity/Searchinfinity_API_Reference |

## Credential constraints

- **Authentication Method: APIKey only**. Each request must carry HTTP header `Authorization: Bearer <ApiKey>`. **Do not** use `X-Api-Key` / `Apikey:`, and **do not** use AK/SK signing (HMAC-SHA256).
- **Interface URL**: `https://torchlight.byteintlapi.com/search_api/web_search` (POST + `Content-Type: application/json`).
- This skill only accepts API Keys issued from the Searchinfinity console (`/search-infinity/api-key`).
- Keys issued by other consoles or product lines are not interchangeable — do not mix them.
- Credentials are used solely for this skill's calls. Never write them to public logs, never echo them in the terminal, and never re-print them inside search results.

## Error code cheat sheet (paired with §9 in SKILL.md)

| Code / message | Action |
|----------------|--------|
| `invalid_api_key` / `700901` Invalid ApiKey | Ask the user to re-copy from [API Key management](https://console.byteplus.com/search-infinity/api-key) and paste again; mind leading/trailing whitespace and quotes |
| `10400` parameter error | Check request structure (e.g. `Filter.TimeRange` must be nested in `Filter`, with the right type) |
| `10403` free quota exhausted | Direct the user to the [activation page](https://console.byteplus.com/search-infinity/web-search) to view / top up the quota |
| `10500` default internal server error | Backend fallback error; brief wait then retry 1–2 times |
| `700429` QPS exceeded | Default 5 QPS; back off with 1s → 2s → 4s |
| Credential not found | Emit the §3 First-time reply template in SKILL.md |

For the full semantics of each error code, refer to the [API reference](https://docs.byteplus.com/en/docs/searchinfinity/Searchinfinity_API_Reference).
