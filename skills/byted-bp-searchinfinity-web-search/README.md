# byted-bp-searchinfinity-web-search

BytePlus Searchinfinity is the official BytePlus-built web search skill for AI applications, delivering structured, source-traceable web results with a clean integration spec.

## Directory layout

```text
byted-bp-searchinfinity-web-search/
├── SKILL.md                  # Agent runtime instructions (main file)
├── references/
│   ├── setup-guide.md        # Detailed activation & configuration steps
│   └── docs-index.md         # Index of official links and error codes
├── scripts/
│   └── web_search.py         # Search script (Authentication Method: APIKey)
└── README.md                 # This file
```

## Official entry points

- Activate the service: https://console.byteplus.com/search-infinity/web-search
- Create an API Key: https://console.byteplus.com/search-infinity/api-key
- API reference: https://docs.byteplus.com/en/docs/searchinfinity/Searchinfinity_API_Reference

## Quick start (3 steps)

1. Drop this directory into your AI application's skills folder
2. Sign in to BytePlus and activate the service: [Searchinfinity Web Search](https://console.byteplus.com/search-infinity/web-search)
3. Open the console to [create an API Key](https://console.byteplus.com/search-infinity/api-key), then **paste the Key directly into the chat with your Agent** — it will bind automatically

If you run into any of the following, please use the live-chat support on the BytePlus console pages above for help:
- A console URL won't open or behaves abnormally
- Service activation fails
- Account permissions or console UI look off

## Quick script test

```bash
cd byted-bp-searchinfinity-web-search
export I18N_WEB_SEARCH_API_KEY="your_api_key"
python3 scripts/web_search.py "latest AI industry news" --time-range OneWeek --count 5
```

For full usage, parameters, and error handling see [SKILL.md](./SKILL.md) and [references/setup-guide.md](./references/setup-guide.md).
