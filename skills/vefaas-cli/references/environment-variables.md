# Environment Variables Reference

## Overview

Environment variables are managed remotely on the function and can be accessed in code via:
- **Node.js**: `process.env.KEY`
- **Python**: `os.environ.get('KEY')`

## Commands

### List All Variables

```bash
vefaas env list

# Output:
# > Environment Variables:
# DATABASE_URL=postgres://user:pass@host:5432/db
# API_KEY=your-api-key
# NODE_ENV=production
```

### Get Single Variable

```bash
vefaas env get DATABASE_URL
# Output: postgres://user:pass@host:5432/db
```

### Set Variable

```bash
vefaas env set KEY VALUE

# Examples:
vefaas env set DATABASE_URL "postgres://user:pass@host:5432/db"
vefaas env set API_KEY "your-api-key"
vefaas env set NODE_ENV "production"
```

### Import from File

```bash
vefaas env import ./env.prod
```

## File Format

The import command supports `.env` file format:

```bash
# Comments are ignored
KEY=VALUE

# Quoted values
API_KEY="your-api-key"
SECRET='single-quoted'

# With export prefix
export NODE_ENV=production

# Database configuration
PGHOST=db.volces.com
PGDATABASE=mydb
PGUSER=admin
PGPASSWORD=secret123
```

Supported formats:
- `KEY=VALUE` - Basic format
- `KEY="VALUE"` or `KEY='VALUE'` - Quoted values
- `export KEY=VALUE` - With export prefix
- `# comment` - Lines starting with `#` are ignored

## Usage in Code

### Node.js

```javascript
const dbUrl = process.env.DATABASE_URL;
const apiKey = process.env.API_KEY;

// With default value
const port = process.env.PORT || 3000;
```

### Python

```python
import os

db_url = os.environ.get('DATABASE_URL')
api_key = os.environ.get('API_KEY')

# With default value
port = int(os.environ.get('PORT', 8000))
```

## Common Patterns

### Database Connection

```bash
vefaas env set PGHOST "db.volces.com"
vefaas env set PGDATABASE "mydb"
vefaas env set PGUSER "admin"
vefaas env set PGPASSWORD "secret"
vefaas env set PGPORT "5432"
```

### API Keys

```bash
vefaas env set API_KEY "your-api-key"
vefaas env set JWT_SECRET "your-jwt-secret"
```

### Feature Flags

```bash
vefaas env set NODE_ENV "production"
vefaas env set DEBUG "false"
```

## Best Practices

1. **Never commit secrets** - Use `vefaas env` instead of config files
2. **Use separate env files** - `env.dev`, `env.staging`, `env.prod`
3. **Import before deploy** - For apps with dependencies:
   ```bash
   vefaas link --newApp my-app --gatewayName $(vefaas run listgateways --first) --yes
   vefaas env import ./env.prod
   vefaas deploy
   ```
