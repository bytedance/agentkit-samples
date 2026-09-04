# Troubleshooting Reference

## Enable Debug Mode

When encountering issues, first enable debug mode with `--debug` or `-d`:

```bash
vefaas --debug deploy
# or
vefaas -d inspect
```

Debug mode outputs:
- **Framework detection**: Detected framework, runtime, build command
- **Shell execution**: Commands, working directory, exit codes
- **Packaging**: Ignore rules, file count, package size
- **HTTP requests/responses**: API call parameters and results

## Debug Log Files

Debug logs are automatically saved to files:

```bash
# Log file location
~/.vefaas/logs/YYYYMMDD-HHMMSS.txt

# View recent logs
ls -lt ~/.vefaas/logs/ | head -5

# View latest log
cat ~/.vefaas/logs/$(ls -t ~/.vefaas/logs/ | head -1)
```

Log files contain full JSON response data (terminal shows preview only).

## Common Issues

### 1. Authentication Failed

**Symptoms**: `InvalidAccessKey` or `SignatureDoesNotMatch` error

**Steps**:
```bash
# Check credential status
vefaas login --check

# Re-login
vefaas login
```

**Common causes**:
- Incorrect AK/SK
- Expired credentials
- Sub-account missing `veFaaSFullAccess` policy

### 2. Framework Detection Failed

**Symptoms**: Incorrect build command or runtime

**Steps**:
```bash
vefaas --debug inspect
```

**Common causes**:
- Missing `package.json` or `requirements.txt`
- Non-standard project structure

**Solution**: Manually specify configuration:
```bash
vefaas deploy --buildCommand "npm run build" --outputPath dist --command "node dist/index.js" --port 3000
```

### 3. Build Failed

**Symptoms**: `command exited with code X` error

**Steps**:
```bash
# View full error with debug mode
vefaas --debug deploy

# Test build command locally
npm run build
```

**Common causes**:
- Dependencies not installed (run `npm install` first)
- Node.js version incompatible
- Missing environment variables

### 4. Deploy Timeout

**Symptoms**: `dependency install timeout` error

**Steps**:
```bash
vefaas --debug deploy
```

**Common causes**:
- Too many Python dependencies or large packages
- Network issues causing slow downloads

**Solution**: Reduce unnecessary dependencies, or pin versions in `requirements.txt`.

### 5. Gateway Not Found

**Symptoms**: `No running gateways found` error

**Steps**:
```bash
vefaas run listgateways
```

**Solution**: Create an API Gateway instance in the [API Gateway console](https://console.volcengine.com/veapig).

## --app vs --func

| Flag | Description | Use Case |
|------|-------------|----------|
| `--app` | Includes web access integration and related resources | Projects created via `vefaas init` or applications in console |
| `--func` | Direct function management | Existing functions, standalone function updates |

- Use `--app` for application-level operations (includes triggers, domains)
- Use `--func` or `--funcId` for function-level operations (code updates only)

Find function name/ID in the function details page, then use `pull` and `deploy` to manage.

## Submit Feedback

If issues persist, collect this information:

```bash
# 1. CLI version
vefaas --version

# 2. Debug log
vefaas --debug <command> 2>&1 | tee debug.log

# 3. Latest log file
cat ~/.vefaas/logs/$(ls -t ~/.vefaas/logs/ | head -1)

# 4. Environment info
node -v
uname -a
```

Include:
- Operating system version
- Node.js version
- Project framework type
