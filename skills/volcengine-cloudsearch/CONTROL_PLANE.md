# Control Plane — ESCloud Instance Management

## Contents

- Use cases and triggers
- Provisioning workflow (multi-step checklist)
- Commands: list, detail, create, scale, delete
- Network: vpc, subnet, zones, node_specs, versions
- Security: ip_allowlist_get, ip_allowlist_set, reset_password
- Nice-to-have ops: nodes, plugins, rename, maintenance_set, deletion_protection_set, restart_node

---

## Use Cases

**Querying infra** ("what specs are available?"): run `node_specs` and `zones`.

**Provisioning** ("create an Elasticsearch/OpenSearch cluster"): follow the **Provisioning Workflow**.

**Inspecting** ("get details for my instance"): run `detail --id <id>`.

**Scaling** ("scale up hot nodes"): confirm the node type and new spec/count → run `scale`.

**Deleting** ("delete instance"): **require explicit user confirmation** → run `delete`.

---

## Provisioning Workflow (Checklist)

Copy this checklist and track progress:

```
Provisioning Progress:
- [ ] Step 0: Fetch supported versions (control.py versions) [recommended]
- [ ] Step 1: Fetch VPCs (control.py vpc)
- [ ] Step 2: Fetch subnets (control.py subnet --vpc-id <id>)
- [ ] Step 3: Fetch zones (control.py zones) [optional]
- [ ] Step 4: Fetch node specs (control.py node_specs)
- [ ] Step 5: Present options and get user choices
- [ ] Step 6: Get instance name + version + admin password
- [ ] Step 7: Create instance (control.py create ...)
- [ ] Step 8: Verify (control.py detail --id <id>)
- [ ] Step 9: Configure IP allowlist (control.py ip_allowlist_set ...)
```

**Step 1**: `control.py vpc` — list available VPCs.

**Step 2**: `control.py subnet --vpc-id <vpc-id>` — list subnets. The CLI uses the subnet to derive `zone_id`.

**Step 4**: `control.py node_specs` — list valid `resource_spec_name` and `storage_spec_name` values. Use these in `create` and `scale`.

**Step 0**: `control.py versions` — best-effort discovery of supported versions derived from `node_specs`. Prefer this over hard-coded version lists since versions may change over time.

**Step 6**: Ask for:
- Instance name
- Version: choose from the output of `control.py versions` / `control.py node_specs` (recommended: pick a stable Elasticsearch 7.x or OpenSearch version).
- Admin password
- Master spec + count (default: 3)
- Hot spec + count (default: 2), plus storage spec + storage size
- Optional Kibana spec (default: 1 node if provided)

**Step 9**: If the data endpoint is not reachable from your network, update IP allowlist using `ip_allowlist_set`.

---

## Output Format

All commands return JSON:

```json
{"status":"success","data":{...}}
```

On error:

```json
{"error":"API Error","details":"..."}
```

---

## Commands

All commands: `{baseDir}/venv/bin/python {baseDir}/scripts/control.py <command>`

### list

```bash
control.py list [--page-number <n>] [--page-size <n>]
```

### detail

```bash
control.py detail --id <instance-id>
```

### vpc

```bash
control.py vpc
```

### subnet

```bash
control.py subnet --vpc-id <vpc-id>
```

### zones

```bash
control.py zones
```

### node_specs

```bash
control.py node_specs
```

### versions

Best-effort list derived from `node_specs` (preferred over hard-coded lists).

```bash
control.py versions
```

### create

```bash
control.py create \
  --name <name> \
  --version <value-from-control.py-versions> \
  --vpc-id <vpc-id> \
  --subnet-id <subnet-id> \
  --admin-password <password> \
  --master-spec <resourceSpecName> \
  [--master-count 3] \
  [--master-storage-spec <storageSpecName>] \
  [--master-storage-size <GiB>] \
  --hot-spec <resourceSpecName> \
  --hot-storage-spec <storageSpecName> \
  --hot-storage-size <GiB> \
  [--hot-count 2] \
  [--kibana-spec <resourceSpecName>] [--kibana-count 1] \
  [--charge-type PostPaid|PrePaid] \
  [--https true|false] \
  [--deletion-protection true|false] \
  [--pure-master true|false]
```

### scale

```bash
control.py scale \
  --id <instance-id> \
  --node-type <Master|Hot|Warm|Cold|Coordinator|Kibana|Other> \
  --spec-name <resourceSpecName> \
  --count <n> \
  [--storage-spec-name <storageSpecName>] \
  [--storage-size <GiB>]
```

### delete

**Low freedom — require explicit user confirmation before executing.**

```bash
control.py delete --id <instance-id> --confirm
```

If deletion fails due to deletion protection, disable it first:

```bash
control.py deletion_protection_set --id <instance-id> --enabled false
```

### ip_allowlist_get

```bash
control.py ip_allowlist_get --id <instance-id>
```

### ip_allowlist_set

```bash
control.py ip_allowlist_set --id <instance-id> --group-name <name> --ips '["1.2.3.4/32","5.6.7.0/24"]' [--type PRIVATE_ES|PUBLIC_ES]
```

### reset_password

```bash
control.py reset_password --id <instance-id> --admin-password <new-password>
```

---

## Observed behaviors (field notes)

These are common patterns and API validations seen in practice. Treat them as troubleshooting hints, not hard guarantees.

- **Status Sensitivity**: Most management actions (rename, scale, restart, allowlist, password) require the instance to be in the `Running` state. If the instance is `Creating` or `Scaling`, these actions may fail with `InstanceNotReady` or `IllegalParameter`.
- **Dedicated Master Nodes**: Production-style clusters usually expect 3 dedicated master nodes.
- **Storage for Scaling**: When scaling the node count of the `Hot` pool, explicit storage parameters (`--storage-spec-name` and `--storage-size`) are often required by the API even if the storage configuration is not changing.
- **Maintenance Windows**: The maintenance window requires full day names (e.g., `MONDAY`, `TUESDAY`). The CLI accepts `Mon,Tue` and normalizes to full uppercase day names.
- **IP Allowlist Migration**: Volcengine ESCloud uses V2 IP allowlists. The `ip_allowlist_set` command defaults to `PRIVATE_ES`; use `--type PUBLIC_ES` if you need to manage a public endpoint allowlist and your instance supports it.
- **Password Constraints**: Passwords often require a combination of uppercase, lowercase, numbers, and special characters, and must be 8-32 characters long.

---

## Nice-to-have operational commands

### nodes

```bash
control.py nodes --id <instance-id>
```

### plugins

```bash
control.py plugins --id <instance-id>
```

### rename

```bash
control.py rename --id <instance-id> --name <new-name>
```

### maintenance_set

```bash
control.py maintenance_set --id <instance-id> --day Mon,Tue --time <value>
```

### deletion_protection_set

```bash
control.py deletion_protection_set --id <instance-id> --enabled true|false
```

### restart_node

```bash
control.py restart_node --id <instance-id> --node-id <node-name> [--force true|false]
```
