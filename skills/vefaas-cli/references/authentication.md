# Authentication Reference

## Authentication Methods

### 1. Interactive Login

```bash
vefaas login
```

Prompts for:
- Access Key ID (AK)
- Secret Access Key (SK)

Credentials are saved to `~/.vefaas/auth.json`.

### 2. Non-Interactive Login

```bash
vefaas login --accessKey YOUR_AK --secretKey YOUR_SK

# With STS session token (optional)
vefaas login --accessKey YOUR_AK --secretKey YOUR_SK --sessionToken YOUR_TOKEN
```

### 3. Environment Variables (Recommended for CI/CD)

```bash
export VOLC_ACCESS_KEY_ID="YOUR_AK"
export VOLC_SECRET_ACCESS_KEY="YOUR_SK"

# Optional: STS token
export VOLC_SESSION_TOKEN="YOUR_STS_TOKEN"
```

When env vars are set, CLI uses them automatically without requiring `vefaas login`.

### 4. OAuth/OIDC Token

```bash
vefaas login --token YOUR_OAUTH_TOKEN
```

### 5. SSO Login

```bash
vefaas login --sso
```

Opens browser for SSO authentication. Useful for organizations with centralized identity management.

## Credential Management

### Check Current Status

```bash
vefaas login --check
```

### Logout

```bash
vefaas logout
```

Clears stored credentials from `~/.vefaas/auth.json`.

## Obtaining Credentials

1. Log in to [Volcengine Console](https://console.volcengine.com)
2. Navigate to **IAM** > **Access Key Management**
3. Create new AK/SK pair
4. Ensure account has **veFaaSFullAccess** policy

## CI/CD Configuration

### GitHub Actions

```yaml
env:
  VOLC_ACCESS_KEY_ID: ${{ secrets.VOLC_ACCESS_KEY_ID }}
  VOLC_SECRET_ACCESS_KEY: ${{ secrets.VOLC_SECRET_ACCESS_KEY }}
```

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `InvalidAccessKey` | Wrong AK | Verify AK in IAM console |
| `SignatureDoesNotMatch` | Wrong SK | Re-check SK value |
| `Request failed with status code 401` | Expired or invalid | Run `vefaas login` again |
| `No valid credentials found` | Not logged in | Run `vefaas login` |
