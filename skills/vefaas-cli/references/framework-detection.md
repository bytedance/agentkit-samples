# Framework Detection Reference

## Overview

vefaas automatically detects project frameworks and configures:
- Build command
- Output directory
- Start command
- Port
- Runtime

Use `vefaas inspect` to see detected settings.

## Inspect Command

```bash
vefaas inspect

# Output:
# > Detected Settings:
# > - Install Command: npm ci
# > - Build Command: npm run build
# > - Output Directory: .next
# > - Start Command: node server.js
# > - Port: 3000
# > - Runtime: native-node20/v1
# > - Framework: next.js
```

JSON output:
```bash
vefaas inspect --json
```

## Supported Frameworks

### Python

| Framework | Runtime | Build Command | Start Command |
|-----------|---------|---------------|---------------|
| FastAPI | native-python3.12/v1 | `./build.sh` | `./run.sh` |
| Django | native-python3.12/v1 | `./build.sh` | `./run.sh` |
| Flask | native-python3.12/v1 | `./build.sh` | `./run.sh` |

### Node.js

| Framework | Runtime | Build Command | Start Command |
|-----------|---------|---------------|---------------|
| Express | native-node20/v1 | - | `node index.js` |
| Next.js | native-node20/v1 | `npm run build` | `node server.js` |
| Nuxt | native-node20/v1 | `npm run build` | `node .output/server/index.mjs` |
| NestJS | native-node20/v1 | `npm run build` | `node dist/main.js` |
| Remix | native-node20/v1 | `npm run build` | `npm start` |
| Vite | native-node20/v1 | `npm run build` | Static serve |
| Astro | native-node20/v1 | `npm run build` | Depends on mode |

### Static Sites

| Framework | Runtime | Build Command | Start Command |
|-----------|---------|---------------|---------------|
| Vitepress | native-node20/v1 | `npx vitepress build` | Caddy serve |
| Rspress | native-node20/v1 | `npm run build` | Caddy serve |
| Create React App | native-node20/v1 | `npm run build` | Caddy serve |
| Angular | native-node20/v1 | `ng build` | Caddy serve |

Static sites use Caddy as the web server. The Caddyfile is auto-generated.

## Override Detection

When auto-detection doesn't match your setup:

### Via Command Line

```bash
vefaas deploy \
  --buildCommand "npm run build:prod" \
  --outputPath dist \
  --command "node dist/server.js" \
  --port 8080 \
  --yes
```

### Via Config

```bash
vefaas config \
  --buildCommand "npm run build:prod" \
  --outputPath dist \
  --command "node dist/server.js" \
  --port 8080
```

## Detection Files

The CLI looks for these files to detect frameworks:

| File | Indicates |
|------|-----------|
| `package.json` | Node.js project |
| `requirements.txt` | Python project |
| `pyproject.toml` | Python project |
| `next.config.js` | Next.js |
| `nuxt.config.ts` | Nuxt |
| `vite.config.ts` | Vite-based |
| `angular.json` | Angular |
| `.vitepress/` | Vitepress |

## Build Environment

Current behavior:
- **Node.js**: Build runs locally, output is packaged and uploaded
- **Python**: Code is uploaded, dependencies installed remotely via `requirements.txt`

## Troubleshooting

**Framework not detected:**
```bash
# Check what's detected
vefaas --debug inspect

# Manually specify
vefaas deploy --buildCommand "..." --command "..." --port 8000 --yes
```

**Wrong build command:**
```bash
# Override in config
vefaas config --buildCommand "npm run build:production"
```

**Missing dependencies:**
```bash
# Ensure package.json or requirements.txt exists
# For Node.js, run npm install first
npm install
vefaas deploy
```
