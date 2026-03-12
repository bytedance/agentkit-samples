---
name: byted-infoquest-search
description: AI-optimized web search and content extraction via BytePlus InfoQuest API. Returns concise, relevant results for AI agents with time filtering and site-specific search. Get API key from https://console.byteplus.com/infoquest/infoquests
---

# Byted InfoQuest

AI-optimized web search and content extraction using BytePlus InfoQuest API. Returns concise, relevant results with time filtering and site-specific search capabilities.

## Environment Variables

Before using this skill, ensure the following environment variable are set:

- `INFOQUEST_API_KEY`: API key for the web search and content extraction service

## Search

```bash
python3 {baseDir}/search.py "query"
python3 {baseDir}/search.py "query" -d 7
python3 {baseDir}/search.py "query" -s github.com
```

## Options

- `-d, --days <number>`: Search within last N days (default: all time)
- `-s, --site <domain>`: Search within specific site (e.g., `github.com`)

## Extract content from URL

```bash
python3 {baseDir}/extract.py "https://example.com/article"
```

## Examples

### Recent News Search
```bash
# Search for AI news from last 3 days
python3 search.py "artificial intelligence news" -d 3
```

### Site-Specific Research
```bash
# Search for Python projects on GitHub
python3 search.py "Python machine learning" -s github.com
```

### Content Extraction
```bash
# Extract content from a single article
python3 extract.py "https://example.com/article"
```

## Notes

### API Access
- **API Key**: Get from https://console.byteplus.com/infoquest/infoquests
- **Documentation**: https://docs.byteplus.com/en/docs/InfoQuest/What_is_Info_Quest
- **About**: InfoQuest is AI-optimized intelligent search and crawling toolset independently developed by BytePlus

### Search Features
- **Time Filtering**: Use `-d` for searches within last N days (e.g., `-d 7`)
- **Site Filtering**: Use `-s` for site-specific searches (e.g., `-s github.com`)

## Quick Setup

1. **Set API key:**
   ```bash
   export INFOQUEST_API_KEY="your-api-key-here"
   ```

2. **Install required Python packages:**
   ```bash
   pip install requests
   ```

3. **Test the setup:**
   ```bash
   python3 search.py "test search"
   ```

## Error Handling

The API returns error messages starting with `"Error:"` for:
- Authentication failures
- Network timeouts
- Empty responses
- Invalid response formats

## Differences from Node.js Version

- **Python 3.6+** required
- **requests** library used instead of fetch
- Simplified argument parsing using argparse
- Same functionality and API endpoints
