---
name: volcengine-cli
description: >-
  Create and manage Volcengine cloud resources using the Volcengine CLI (`ve` command). Supports all
  Volcengine services including ECS, VPC, CLB, RDS, Redis, and more. Trigger this skill whenever the
  user asks to create, query, modify, or delete cloud resources on Volcengine, mentions the `ve` command,
  says "volcengine CLI", or describes infrastructure tasks such as "create an ECS instance",
  "set up a VPC", "list security groups", "allocate an EIP". Also trigger when the user encounters
  errors from `ve` commands and needs troubleshooting help.
argument-hint: <task description, e.g., "create an ECS instance in the Beijing region">
user-invocable: true
allowed-tools: Bash, Read, Write
---

# Volcengine CLI Skill

Create and manage Volcengine cloud resources by calling Volcengine OpenAPIs through the `ve` command.

---

## 0. Install the ve CLI

If the `ve` command is not available on the system:

**Option 1: npm (recommended)**
```bash
npm i -g @volcengine/cli
```

**Option 2: GitHub Releases**
Download: https://github.com/volcengine/volcengine-cli/releases

Verify the installation: `ve --version`

---

## 1. Initialization (run at the start of every session)

Run the identity verification command to confirm that credentials are usable:

```bash
ve sts GetCallerIdentity
```

**Success** -> inform the user of the current account identity and region, then proceed with the task.

> **Switching regions**: the `--region` flag and the `VOLCENGINE_REGION` environment variable do not override the region in the config file. Switch regions via `ve configure profile --profile <name>`. Use `ve configure list` to view available profiles.

**Failure** -> credentials are not configured or invalid. Guide the user through one of the following:

**Option 1: Environment variables** (recommended for temporary use)
```bash
export VOLCENGINE_ACCESS_KEY_ID="<YOUR_AK>"
export VOLCENGINE_SECRET_ACCESS_KEY="<YOUR_SK>"
export VOLCENGINE_REGION="cn-beijing"
```

**Option 2: Config file** (persistent)

If `~/.volcengine/config.json` does not exist, create an empty template for the user to fill in:

```bash
mkdir -p ~/.volcengine
cat > ~/.volcengine/config.json << 'EOF'
{
  "current": "default",
  "profiles": {
    "default": {
      "name": "default",
      "mode": "ak",
      "access-key": "<YOUR_AK>",
      "secret-key": "<YOUR_SK>",
      "region": "cn-beijing",
      "endpoint": "",
      "session-token": "",
      "disable-ssl": false
    }
  },
  "enableColor": false
}
EOF
```

> **Never read `~/.volcengine/config.json`** — the file contains sensitive credentials. Only create an empty template; never read an existing config.

---

## 2. Safety Rules (mandatory)

### Read/Write Classification

| Level | Operation Types | Behavior |
|-------|----------------|----------|
| **Read-only** | Describe\* / List\* / Get\* / Query\* | Execute directly, no confirmation needed |
| **Write** | Create\* / Run\* / Allocate\* / Attach\* / Associate\* / Authorize\* | Show the full command and wait for user confirmation |
| **Destructive** | Delete\* / Terminate\* / Release\* / Revoke\* / Modify\* / Stop\* / Detach\* | Show command + impact summary; **require** user confirmation |

### Core Principles

1. **Default to read-only** — unless the user explicitly requests a change, execute in read-only mode
2. **DryRun first** — if a write/destructive operation supports `--DryRun true`, run a DryRun to preview the plan, then confirm before executing
3. **Confirm before executing** — show the full command for write operations and wait for approval
4. **Protect credentials** — never read `~/.volcengine/config.json`; never expose access-key, secret-key, or session-token in output

### DryRun Notes

A successful DryRun validation returns **exit code 1** (non-zero) with `DryRunOperation` in stderr. This is expected behavior:

```bash
output=$(ve <svc> <action> --DryRun true ... 2>&1)
if echo "$output" | grep -q "DryRunOperation"; then
  echo "Parameter validation passed"
fi
```

---

## 3. Locate APIs and Retrieve Parameters

### Locate the API (find the service name + Action name)

```
Step 1: Service name + Action known? -> Use them directly; skip to "Retrieve parameters"
Step 2: Service name known, Action unknown?
  -> ve <service> 2>&1 | grep -i <keyword>
Step 3: Service name also unknown?
  -> ve 2>&1 | grep -i <service keyword>
Step 4: None of the above work?
  -> python3 scripts/find_api.py <keyword>
```

### Retrieve parameters (once the Action is known)

Choose a strategy based on operation type:

| Operation Type | Strategy | Rationale |
|---------------|----------|-----------|
| **Read-only** (Describe/List/Get) | `ve <svc> <action> --help` | Few, simple parameters — names alone are sufficient |
| **Write/destructive** (Create/Run/Delete, etc.) | `scripts/fetch_swagger.py` for full docs | Many parameters, nested structures — need required fields, examples, and descriptions |
| **Still unclear after `--help`** | Supplement with `scripts/fetch_swagger.py` | Use whenever parameter meaning is uncertain |
| **Errors like `Invalid*` / `Missing*`** | Recheck with `scripts/fetch_swagger.py` | On `InvalidParameter`, `InvalidXxx.NotFound`, or `MissingParameter`, verify parameter names, required fields, and value ranges |

```bash
# Read-only — --help is sufficient
ve ecs DescribeInstances --help

# Write — retrieve full documentation
python3 scripts/fetch_swagger.py --service ecs --action RunInstances
```

### ve command name and API version relationship

- Default version -> ve command = base service name (e.g., `iam`)
- Non-default version -> ve command = `service name + version without hyphens` (e.g., `iam` v2021-08-01 -> `iam20210801`)
- When in doubt: `ve 2>&1 | grep <service>` to confirm

### Python helper usage

```bash
# Search for an API (when the service name is unknown)
python3 scripts/find_api.py <keyword> [--limit N]

# Get full API parameter documentation (when descriptions/examples are needed)
python3 scripts/fetch_swagger.py --service <ServiceCode> --action <ActionName>

# List all APIs for a service
python3 scripts/fetch_swagger.py --service <ServiceCode> --list
```

> Always pass the **base service name** to scripts/fetch_swagger.py (e.g., `--service iam`, not `iam20210801`) — the script auto-detects the version.

---

## 4. Execute API Calls

### Basic Format

```bash
ve <ServiceCode> <ActionName> --ParamName "value"
```

### Parameter Passing Rules

Determine the format from `--help` output:
- **Flat parameter format**: `--help` lists individual `--Key type` entries (e.g., ECS, VPC, IAM) -> pass with `--Key "value"`
- **JSON format**: `--help` only shows `--body '{...}'` (e.g., Redis, CR, and other POST APIs) -> pass with `--body '{...}'`

```bash
# Flat parameters — nested fields use dot notation; arrays use .N index (starting from 1)
ve ecs RunInstances --Placement.ZoneId "cn-beijing-a"
ve ecs RunInstances --NetworkInterfaces.1.SubnetId "subnet-xxxx"
ve ecs RunInstances --Tags.1.Key "env" --Tags.2.Key "app"

# JSON format (when --help only shows --body)
ve redis CreateDBInstance --body '{"InstanceName":"demo", "RegionId":"cn-beijing", ...}'
```

### Response Format

```json
// Success
{ "ResponseMetadata": { "RequestId": "..." }, "Result": { ... } }

// Failure
{ "ResponseMetadata": { "Error": { "Code": "...", "Message": "..." } } }
```

### Async Resource Creation Requires Polling

Some resources (VKE clusters, RDS instances, ECS instances, etc.) take several minutes to create. After creation, poll the Describe endpoint until the resource reaches the desired status before proceeding.

> Creating sub-resources (e.g., security groups) immediately after VPC creation may fail with `InvalidVpc.InvalidStatus`. Create sub-resources sequentially (subnet first, then security group), or wait a few seconds and retry.

```bash
# General polling pattern: check every 30 seconds until the target status is reached
while true; do
  cur_status=$(ve <svc> Describe<Resource> --<IdParam> "xxx" 2>&1 | grep -o '"Status":"[^"]*"')
  echo "$(date +%H:%M:%S) $cur_status"
  echo "$cur_status" | grep -q '"Status":"Running"' && break
  sleep 30
done
```

---

## 5. End-to-End Execution Flow (Summary)

```
1. Initialize: verify credentials -> GetCallerIdentity -> confirm region
2. Understand the task: is the user querying or making changes?
3. Locate the API: ve --help first -> Python helpers as fallback
4. Query dependent resources: use Describe*/List* to obtain required IDs
5. Read operation -> execute directly and display results
   Write operation -> show command -> DryRun (if supported) -> user confirmation -> execute
6. Parse the response and report results to the user
```

---

## 6. Service-Specific Notes

Consult or update the corresponding notes file when encountering service-specific issues:

- ECS: [notes/ecs.md](notes/ecs.md)
- IAM: [notes/iam.md](notes/iam.md)
- Redis: [notes/redis.md](notes/redis.md)
