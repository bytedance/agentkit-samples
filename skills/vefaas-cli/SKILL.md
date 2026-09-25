---
name: vefaas
description: Deploy and manage serverless applications on Volcengine veFaaS. Use when the user wants to deploy web apps, manage functions (pull code, upload and deploy), configure environment variables, or work with veFaaS services.
allowed-tools: Bash(vefaas:*)
---

# vefaas: Volcengine FaaS CLI

**vefaas** is the command-line tool for Volcengine Function Service (veFaaS). It enables serverless application deployment, function management, and configuration through a streamlined workflow.

## Installation

```bash
npm i -g https://vefaas-cli.tos-cn-beijing.volces.com/volcengine-vefaas-latest.tgz
```

Verify installation:
```bash
vefaas --version
```

## Core Workflow

The typical deployment pattern:

1. **Check Node.js**: `node --version` (requires >= 18, recommended 20+)
   - If version is too low, switch using nvm (`nvm use 20`) or fnm (`fnm use 20`), or manually install a newer version
2. **Check CLI**: `vefaas --version` to verify installation
3. **Check Auth**: `vefaas login --check` to verify login status
   - If not logged in, run `vefaas login --sso` (opens browser, auto-completes when user authorizes - no manual input needed)
4. **Deploy**: `vefaas deploy --newApp <name> --gatewayName $(vefaas run listgateways --first) --yes`
5. **Access**: `vefaas domains` to view URLs

## Quick Commands

| Purpose | Command |
|---------|---------|
| Check auth | `vefaas login --check` |
| Login (SSO) | `vefaas login --sso` (non-interactive: opens browser, auto-completes when authorized, **recommended**) |
| Login (AK/SK) | `vefaas login --accessKey <AK> --secretKey <SK>` |
| Init from template | `vefaas init --template <name>` |
| Deploy new app | `vefaas deploy --newApp <name> --gatewayName $(vefaas run listgateways --first) --yes` |
| Deploy existing | `vefaas deploy --app <name> --yes` |
| List gateways | `vefaas run listgateways --first` |
| View URLs | `vefaas domains` |
| Set env var | `vefaas env set KEY VALUE` |
| View config | `vefaas config list` |
| Pull code | `vefaas pull --func <name>` |
| Inspect project | `vefaas inspect` |

## Global Options

| Option | Description |
|--------|-------------|
| `-d, --debug` | Enable debug mode for troubleshooting |
| `--yes` | Non-interactive mode (required for CI/AI coding) |
| `--region` | Region override (e.g., cn-beijing) |

## Cookbooks

Step-by-step guides for common scenarios:

- **[Template Quickstart](cookbooks/template-quickstart.md)** - Create and deploy from official templates
- **[Deploy Existing Code](cookbooks/deploy-existing-code.md)** - Deploy your existing project
- **[Manage Functions](cookbooks/manage-functions.md)** - Manage functions (pull code, upload and deploy)

## References

Detailed documentation on specific topics:

- **[Authentication](references/authentication.md)** - Login methods and credentials
- **[Configuration](references/configuration.md)** - Config files and settings
- **[Environment Variables](references/environment-variables.md)** - Managing env vars
- **[Framework Detection](references/framework-detection.md)** - Supported frameworks and auto-detection
- **[Troubleshooting](references/troubleshooting.md)** - Debug mode, common issues, and solutions

## Important Notes

- Always use `--yes` for non-interactive mode in CI/CD and AI coding scenarios
- Use `$(vefaas run listgateways --first)` to get an available gateway
- Config is stored in `.vefaas/config.json` after linking
- Use `--debug` or `-d` to troubleshoot issues
