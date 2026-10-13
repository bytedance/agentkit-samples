# Cookbook: Template Quickstart

Create and deploy a serverless application from official templates.

## Prerequisites

- vefaas CLI installed
- Valid credentials (AKSK/SSO)

## Scenario: Create a FastAPI Application

### Step 1: Login

```bash
# Interactive login
vefaas login

# Or non-interactive
vefaas login --accessKey YOUR_AK --secretKey YOUR_SK

# Or via environment variables (recommended for CI)
export VOLC_ACCESS_KEY_ID="YOUR_AK"
export VOLC_SECRET_ACCESS_KEY="YOUR_SK"
```

### Step 2: Initialize from Template

```bash
# Interactive - shows template list
vefaas init

# Non-interactive - specify template name
vefaas init --template FastAPI

# With auto dependency install
vefaas init --template FastAPI --installDeps
```

Available templates include:
- **FastAPI** - Python web framework for APIs
- **Express** - Node.js web framework
- **Vitepress** - Static documentation generator
- **Next.js** - React framework
- **Nuxt** - Vue framework

### Step 3: Deploy

```bash
cd <project-directory>

# One-liner deployment
vefaas deploy --newApp my-fastapi-app --gatewayName $(vefaas run listgateways --first) --yes
```

### Step 4: Access Your Application

```bash
vefaas domains
# Output:
# > Access URL: https://xxxxxxx.apigateway-cn-beijing.volceapi.com/
```

## Complete Example

```bash
# Full workflow
vefaas login --check

vefaas init --template FastAPI
cd fastapi

vefaas deploy --newApp fastapi-demo --gatewayName $(vefaas run listgateways --first) --yes

vefaas domains
```

## Local Development

After initialization, develop locally before redeploying:

**Python (FastAPI/Django/Flask):**
```bash
pip install -r requirements.txt
python main.py
# or: uvicorn app:app --reload
```

**Node.js (Express/Next.js/Nuxt):**
```bash
npm install
npm run dev
```

Then redeploy changes:
```bash
vefaas deploy
```
