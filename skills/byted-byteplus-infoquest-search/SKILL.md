---
name: byted-byteplus-infoquest-search
description: AI-optimized web search, image search and content extraction via BytePlus InfoQuest API. Use this skill when you need to gather concise and up-to-date information from the web, find images, or extract clean content from specific URLs.
---

# Byted InfoQuest

AI-optimized web search, image search and content extraction using BytePlus InfoQuest API. Returns concise, relevant results with time filtering, site-specific search, and image search capabilities.

> **Tip**: InfoQuest is currently not available in Mainland China regions.

## Environment Variables

Before using this skill, ensure the following environment variable are set:

- `INFOQUEST_API_KEY`: API key for the web search, image search and content extraction service

## Web Search

```bash
python3 scripts/search.py "query"
python3 scripts/search.py "query" -d 7
python3 scripts/search.py "query" -s github.com
```

## Image Search

```bash
python3 scripts/search.py "query" -i
python3 scripts/search.py "query" -i -z l
python3 scripts/search.py "query" -i -s unsplash.com -d 30
```

## Options

- `-d, --days <number>`: Search within last N days (default: all time)
- `-s, --site <domain>`: Search within specific site (e.g., `github.com`, `unsplash.com`)
- `-i, --image`: Perform image search (default: web search)
- `-z, --image-size <size>`: Image size filter: `l` (large), `m` (medium), `i` (icon)

## Extract content from URL

```bash
python3 scripts/extract.py "https://example.com/article"
```

## Examples

### Recent News Search
```bash
# Search for AI news from last 3 days
python3 scripts/search.py "artificial intelligence news" -d 3
```

### Site-Specific Research
```bash
# Search for Python projects on GitHub
python3 scripts/search.py "Python machine learning" -s github.com
```

### Image Search Examples
```bash
# Search for cat images
python3 scripts/search.py "cat" -i

# Search for large landscape images
python3 scripts/search.py "landscape" -i -z l

# Search for icons from specific site
python3 scripts/search.py "logo" -i -z i -s github.com

# Search for recent images
python3 scripts/search.py "sunset" -i -d 7
```

### Content Extraction
```bash
# Extract content from a single article
python3 scripts/extract.py "https://example.com/article"
```

## Notes

### API Access
- **API Key**: Get from https://console.byteplus.com/infoquest/infoquests
- **Documentation**: https://docs.byteplus.com/en/docs/InfoQuest/What_is_Info_Quest
- **About**: InfoQuest is AI-optimized intelligent search and crawling toolset independently developed by BytePlus

### Search Features
- **Time Filtering**: Use `-d` for searches within last N days (e.g., `-d 7`)
- **Site Filtering**: Use `-s` for site-specific searches (e.g., `-s github.com`)
- **Image Search**: Use `-i` for image search, with optional size filtering (`-z`)
- **Image Size Options**: `l` (large), `m` (medium), `i` (icon)

### Image Search Usage
Image search returns URLs to images that can be used as reference for image generation. Each result includes:
- `title`: Image title or description
- `image_url`: Direct URL to the image

**Usage hint**: Use the `image_url` values as reference images in image generation. Download them first if needed.

## Quick Setup

1. **Set API key:**
   ```bash
   export INFOQUEST_API_KEY=<REPLACE_WITH_YOUR_KEY>
   ```

2. **Install required Python packages:**
   ```bash
   pip install requests
   ```

3. **Test the setup:**
   ```bash
   # Test web search
   python3 scripts/search.py "test search"
   
   # Test image search
   python3 scripts/search.py "test" -i
   ```

## Error Handling

The API returns error messages starting with `"Error:"` for:
- Authentication failures
- Network timeouts
- Empty responses
- Invalid response formats
- Invalid image size parameters (must be 'l', 'm', or 'i')

## Differences from Node.js Version

- **Python 3.6+** required
- **requests** library used instead of fetch
- Simplified argument parsing using argparse
- Same functionality and API endpoints