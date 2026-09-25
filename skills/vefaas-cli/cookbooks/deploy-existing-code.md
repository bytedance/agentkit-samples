# Cookbook: Deploy Existing Code

Deploy your existing project to veFaaS with automatic framework detection.

## Prerequisites

- vefaas CLI installed
- Valid credentials (AKSK/SSO)
- Existing project with supported framework

## Scenario A: Simple Deployment (No Env Dependencies)

For projects without database or external service dependencies.

### One-liner Deployment

```bash
cd your-project

# Deploy with auto-detection
vefaas deploy --newApp my-app --gatewayName $(vefaas run listgateways --first) --yes
```

The CLI will:
1. Auto-detect framework (Next.js, Nuxt, FastAPI, etc.)
2. Configure build command and output path
3. Run local build
4. Package and upload
5. Deploy and return access URL

> [!NOTE]
> - **Static sites**: Auto-detected static projects (Vite, Vitepress, etc.) will be served via auto-generated Caddyfile
> - **Server apps**: If your app requires server logic, ensure it listens on port **8000** by default

### Verify Detection

```bash
# Check what vefaas detected
vefaas inspect

# Output:
# > Detected Settings:
# > - Build Command: npm run build
# > - Output Directory: .next
# > - Start Command: node server.js
# > - Port: 3000
# > - Runtime: native-node20/v1
# > - Framework: next.js
```

## Scenario B: With Environment Dependencies

For projects requiring database connections, API keys, etc.

### Step 1: Link Without Deploying

```bash
cd your-project

# Create app and link, but don't deploy yet
vefaas link --newApp my-app --gatewayName $(vefaas run listgateways --first) --yes
```

### Step 2: Configure Environment Variables

```bash
# Set individual variables
vefaas env set DATABASE_URL "postgres://user:pass@host:5432/db"
vefaas env set API_KEY "your-api-key"

# Or import from .env file
vefaas env import ./.env.prod
```

Example `.env.prod` file:
```
PGHOST=db.volces.com
PGDATABASE=mydb
PGUSER=admin
PGPASSWORD=secret
API_KEY="your-api-key"
```

### Step 3: Deploy

```bash
vefaas deploy
```

## Scenario C: Custom Build Configuration

When auto-detection doesn't match your setup.

### Override via Command Line

```bash
vefaas deploy \
  --newApp my-app \
  --gatewayName $(vefaas run listgateways --first) \
  --buildCommand "npm run build" \
  --outputPath dist \
  --command "node dist/index.js" \
  --port 3000 \
  --yes
```

### Or Configure Persistently

```bash
# Set config first
vefaas config --buildCommand "npm run build" --outputPath dist --command "node dist/index.js" --port 3000

# Then deploy
vefaas deploy --newApp my-app --gatewayName $(vefaas run listgateways --first) --yes
```

## Scenario D: Deploy to Existing Application

When you already have a veFaaS application.

```bash
# By app name
vefaas deploy --app my-existing-app --yes

# By app ID
vefaas deploy --appId app-xxxxx --yes
```

## Supported Frameworks

| Framework | Runtime | Auto-detected |
|-----------|---------|---------------|
| FastAPI | native-python3.12/v1 | Yes |
| Django | native-python3.12/v1 | Yes |
| Flask | native-python3.12/v1 | Yes |
| Express | native-node20/v1 | Yes |
| Next.js | native-node20/v1 | Yes |
| Nuxt | native-node20/v1 | Yes |
| NestJS | native-node20/v1 | Yes |
| Remix | native-node20/v1 | Yes |
| Vite | native-node20/v1 | Yes |
| Astro | native-node20/v1 | Yes |
| Vitepress | native-node20/v1 | Yes |
| Angular | native-node20/v1 | Yes |
