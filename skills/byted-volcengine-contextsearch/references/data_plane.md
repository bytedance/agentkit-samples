# Data Plane - Context Search Runtime

Use this guide for the bundled Context Search data-plane scripts: search context-aware indexes and optionally chat with RAG-backed knowledge bases.

## Contents

- When to use this document
- Quick start
- Configuration
- Commands
- Mode descriptions
- Intent routing
- Safety and error handling

## When to use this document

Use `data.py` or `context_search.py` when the user asks to:
- Search a configured knowledge base, image context, or video context.
- Chat with a RAG-backed knowledge base.
- List configured data-plane contexts.

Do not use this document for application console operations such as creating AgenticSearch scenes, data sources, indexers, search configs, tools, skills, or API keys. Those belong to [control_plane.md](control_plane.md).

## Quick start

The data-plane script from the provided skill is available as both:

```bash
{baseDir}/venv/bin/python {baseDir}/scripts/data.py <command>
{baseDir}/venv/bin/python {baseDir}/scripts/context_search.py <command>
```

If `{baseDir}/venv` does not exist:

```bash
python3 -m venv {baseDir}/venv
{baseDir}/venv/bin/pip install -r {baseDir}/requirements.txt
```

## Configuration

Set the data-plane API key:

```bash
export CTX_SEARCH_API_KEY='your-api-key-here'
```

Create `{baseDir}/config.json` from `{baseDir}/config.json.template`:

```json
{
  "contexts": {
    "default": {
      "type": "knowledge_base",
      "base_url": "https://your-api-endpoint.com",
      "description": "Default context service"
    },
    "knowledge-base-a": {
      "type": "knowledge_base",
      "base_url": "https://another-endpoint.com",
      "description": "Knowledge base A for technical docs"
    },
    "image-index": {
      "type": "image",
      "base_url": "https://image.example.com",
      "description": "Image search context"
    }
  }
}
```

Context type rules:
- Empty or missing `type`: knowledge base. Supports `search` and `chat`.
- `knowledge_base`: knowledge base. Supports `search` and `chat`.
- `image`: image context. Supports `search` only.
- `video`: video context. Supports `search` only.

## Commands

List configured contexts:

```bash
data.py list
data.py list --json
```

Search:

```bash
data.py search \
  --context <context-name> \
  --text "your search query" \
  --mode <quick|normal|deep> \
  --size <number-of-results>
```

For all data-plane requests, omit `--mode` and `--size` unless the user asks for a specific mode or result count; the service default is used when they are omitted. For `image` and `video` contexts, only pass `--mode quick` when the user explicitly asks for quick mode; other modes are not supported.

For `image` and `video` contexts, the script automatically adds `return_download_info: true`. It also sets `use_public_download_url: true` when the configured `base_url` host ends with `.volces.com`, otherwise `false`.

Chat:

```bash
data.py chat \
  --context <context-name> \
  --message "your message" \
  --mode <quick|normal|deep> \
  --size <number-of-results> \
  --stream
```

Use `--json` when downstream automation needs raw response JSON.

## Mode descriptions

- `quick`: fast response, suitable for simple queries.
- `normal`: balanced speed and quality.
- `deep`: comprehensive search or chat, best for complex queries.

## Intent routing

- "有哪些知识库/上下文可用" -> `data.py list`.
- "检索/搜索/查一下某知识库" -> `data.py search`.
- "基于知识库问答/聊一下" -> `data.py chat`.
- "图片/视频上下文检索" -> `data.py search`; do not use chat.
- "创建 AgenticSearch/数据源/索引/SearchConfig" -> [control_plane.md](control_plane.md).

## Safety and error handling

- Never invent `base_url`, API keys, context names, or request credentials.
- If `CTX_SEARCH_API_KEY` is missing, ask the user to configure it.
- If `config.json` is missing, tell the user to create it from `config.json.template`.
- If a context is `image` or `video`, do not run `chat`; use `search`. Only pass `--mode quick` if the user explicitly asks for it.
- Surface HTTP and network errors as returned by the script.
