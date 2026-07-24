# Cookbook: Manage Functions

Pull, modify, and redeploy existing veFaaS functions.

## Prerequisites

- vefaas CLI installe
- Valid credentials (AKSK/SSO)
- Existing function in veFaaS console

## Scenario A: Pull and Modify Function Code

### Step 1: Pull Function Code

```bash
# By function name
vefaas pull --func my-function-name

# By function ID
vefaas pull --funcId func-xxxxx
```

This creates a directory with the function code:
```
my-function-name/
├── app.py (or index.js)
├── requirements.txt (or package.json)
├── run.sh
└── .vefaas/
    └── config.json
```

### Step 2: Modify Code

```bash
cd my-function-name
# Edit your code
```

### Step 3: Redeploy

```bash
vefaas deploy
# or with explicit function reference
vefaas deploy --func my-function-name --yes
```

## Scenario B: Push Code to Existing Function

> [!NOTE]
> `push` only uploads code without triggering deployment. For most cases, use `deploy` instead.

```bash
# Push code only (no deployment)
vefaas push --func my-function-name --yes
```

## Scenario C: Manage Environment Variables

### List Variables

```bash
vefaas env list
# Output:
# > Environment Variables:
# DATABASE_URL=postgres://...
# API_KEY=xxx
```

### Get Single Variable

```bash
vefaas env get DATABASE_URL
```

### Set Variables

```bash
# Set single variable
vefaas env set NEW_KEY "new-value"

# Update existing variable
vefaas env set DATABASE_URL "new-connection-string"
```

### Import from File

```bash
vefaas env import .env
```

## Scenario D: View and Update Configuration

### View Current Config

```bash
vefaas config list

# Output:
# > Config Summary:
# - Application ID: app-xxxxx
# - Function ID: func-xxxxx
# - Region: cn-beijing
# - Gateway ID: gw-xxxxx
# - System URL: https://xxx.apigateway-cn-beijing.volceapi.com/
#
# > Remote Function Settings:
# - Build Command: npm run build
# - Output Directory: dist
# - Start Command: node dist/index.js
# - Port: 3000
```

### Pull Config from Cloud

```bash
# By app name
vefaas config pull --app my-app

# By function name
vefaas config pull --func my-function
```

### Update Settings

```bash
vefaas config --buildCommand "npm run build:prod" --port 8080
```

## Scenario E: Debug Issues

### Enable Debug Mode

```bash
vefaas --debug deploy
# or
vefaas -d inspect
```

### View Debug Logs

```bash
# Logs are saved to ~/.vefaas/logs/
ls -lt ~/.vefaas/logs/ | head -5

# View latest log
cat ~/.vefaas/logs/$(ls -t ~/.vefaas/logs/ | head -1)
```

### Common Issues

**Authentication Failed:**
```bash
vefaas login --check
vefaas login  # Re-authenticate
```

**Framework Not Detected:**
```bash
vefaas inspect  # Check detection
vefaas deploy --buildCommand "..." --command "..." --port 8000 --yes
```
