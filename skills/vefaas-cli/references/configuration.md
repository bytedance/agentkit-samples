# Configuration Reference

## Config File Location

After linking, config is stored in `.vefaas/config.json` in your project root.

## Config File Structure

```json
{
  "version": "1.0",
  "function": {
    "id": "func-xxxxx",
    "runtime": "native-node20/v1",
    "region": "cn-beijing",
    "application_id": "app-xxxxx"
  },
  "triggers": {
    "type": "apig",
    "system_url": "https://xxx.apigateway-cn-beijing.volceapi.com/",
    "id": "gw-xxxxx"
  }
}
```

## Field Reference

| Field | Description |
|-------|-------------|
| `version` | Config file version (currently `1.0`) |
| `function.id` | Function ID |
| `function.runtime` | Runtime (e.g., `native-node20/v1`, `native-python3.12/v1`) |
| `function.region` | Deployment region (e.g., `cn-beijing`) |
| `function.application_id` | Application ID |
| `triggers.type` | Trigger type (`apig` for HTTP) |
| `triggers.system_url` | Public access URL |
| `triggers.inner_url` | Internal VPC URL |
| `triggers.id` | API Gateway instance ID |

## Commands

### View Config

```bash
vefaas config list
```

### Pull Config from Cloud

```bash
# By app name
vefaas config pull --app my-app

# By app ID
vefaas config pull --id app-xxxxx

# By function name
vefaas config pull --func my-function

# By function ID
vefaas config pull --funcId func-xxxxx
```

### Update Settings

```bash
vefaas config --buildCommand "npm run build" --outputPath dist --command "node dist/index.js" --port 8000
```

### Available Settings

| Option | Description |
|--------|-------------|
| `--buildCommand` | Local build command |
| `--outputPath` | Build output directory |
| `--command` | Remote start command |
| `--port` | Listening port |
| `--runtime` | Runtime override |

## Configuration Priority

From highest to lowest:

1. **Command line flags** (`--buildCommand`, `--port`, etc.)
2. **Cloud function config** (synced via `config pull` or `deploy`)
3. **Local detection** (via `vefaas inspect`)
4. **Default values**

## Ignore Files

### .vefaasignore

Controls which files are excluded from upload. Format is similar to `.gitignore`:

```
# Local config
*.local
.env.local

# Dependencies
node_modules/
__pycache__/
.venv/

# Build cache
.next/
dist/
```

### Default Ignore Rules

These are always ignored (no config needed):

| Category | Patterns |
|----------|----------|
| Version control | `.git/`, `.svn/`, `.hg/` |
| Python | `.venv/`, `site-packages/`, `__pycache__/` |
| IDE | `.idea/`, `.vscode/`, `*.swp` |
| System | `.DS_Store`, `Thumbs.db` |
| CLI | `.vefaas/` |
