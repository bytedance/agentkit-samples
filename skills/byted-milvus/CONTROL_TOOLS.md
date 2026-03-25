# Low-Level API Reference

Tool-based CLI for direct API-shaped access. This document is exclusively for `control_tools.py`. Use it only when goal-based `control.py` does not cover a specific operation.

```bash
{baseDir}/venv/bin/python {baseDir}/scripts/control_tools.py <command>
```

All commands return JSON:

```json
{"status": "success", "data": { ... }}
```

On error:

```json
{"error": "API Exception", "details": "..."}
```

---

## Regular Milvus

### list

```bash
control_tools.py list [--page-number <n>] [--page-size <n>]
```

Defaults: page 1, size 10. If `total > page_number * page_size`, fetch next page.

### create

```bash
control_tools.py create --name <name> --vpc-id <vpc-id> --subnet-id <subnet-id> --cpu <cores> --mem <gb> --password <password> [--version <value>] [--cu-type PERFORMANCE/CAPACITY] [--ha true/false]
```

- `--cpu` and `--mem` are integers (e.g. `--cpu 4 --mem 16` = 4 cores, 16GB).
- `--cu-type` is optional. If omitted, the API typically defaults to `PERFORMANCE`.
- If user says specs in loose formats like `"2c8g"`, `"4核16G"`, `"4 CPU 16GB"`, extract the CPU and memory numbers.
- The script auto-resolves the required `ResourceSpecName` per node type using the V2 spec API. If the requested cpu/mem is below the minimum for a node type (e.g. INDEX_NODE), it selects the closest matching spec.
- `--ha` defaults to **true**. Pass `--ha false` only if user explicitly wants non-HA.

### delete

**Low freedom — execute exactly as shown.**

```bash
control_tools.py delete --id <instance-id> --confirm <instance-id>
```

If API returns `TaskIsRunning`, inform user to retry when status is `Running`.

### detail

```bash
control_tools.py detail --id <instance-id>
```

### scale

```bash
control_tools.py scale --id <instance-id> --type <node-type> --cpu <cores> --mem <gb> --count <nodes> [--cu-type PERFORMANCE/CAPACITY] [--ha true/false]
```

- `--cu-type` is optional. If omitted, the instance class remains unchanged.
- Only run scaling when instance status is `Running`. If status is `Scaling`, wait; concurrent operations may return `InstanceOperationForbidden`.
- Prefer one scaling dimension per operation: change **either** CPU/mem (vertical) **or** node count (horizontal), then wait for `Running` and verify via `detail`.
- The script auto-resolves the required `ResourceSpecName` for the target node type using the V2 spec API.
- Observed constraints/pitfalls:
  - `META_NODE` upgrades: single-instance mode supported up to **4C16G**. To go beyond, enable HA and use at least **2 nodes** (otherwise you may see `NodeNumTooSmall`).
  - `DATA_NODE` changes: if `NodeNumTooSmall` occurs during a downgrade/resize, split the plan into two sequential operations (vertical then horizontal, or vice versa) and retry after the instance returns to `Running`.

Node types: `QUERY_NODE`, `DATA_NODE`, `INDEX_NODE`, `PROXY_NODE`, `META_NODE`.

### vpc

```bash
control_tools.py vpc
```

### subnet

```bash
control_tools.py subnet --vpc-id <vpc-id>
```

### versions

```bash
control_tools.py versions
```

### specs

```bash
control_tools.py specs
```

Returns V2 spec data including `ResourceSpecName` per node type. Note: INDEX_NODE and QUERY_NODE have different spec families and higher minimum CPU than META/PROXY/DATA nodes (see `NodeSupportSpecList` in the response).

---

## Serverless (MS*) Commands

These commands operate on **Milvus Serverless** instances via the `MS*` APIs.

### ms-list (MSDescribeInstances)

```bash
control_tools.py ms-list [--page-number <n>] [--page-size <n>] [--instance-id <id>] [--instance-name <name>] [--project-name <name>]
```

### ms-detail (MSDescribeInstance)

```bash
control_tools.py ms-detail --id <instance-id> [--project-name <name>]
```

### ms-create-one-step (MSCreateInstanceOneStep)

```bash
control_tools.py ms-create-one-step --name <name> --password <password> --version V2_5 --vpc-id <vpc-id> --subnet-id <subnet-id> [--project-name default] [--delete-protect true/false]
```

Notes:
- `--version` allowed values: `V2_5`, `V2_6`.
- This MS one-step create does **not** require specifying `zones` in the request model.

### ms-release (MSReleaseInstance)

**Destructive. Requires explicit confirmation.**

```bash
control_tools.py ms-release --id <instance-id> --confirm <instance-id>
```

### ms-modify-public-domain (MSModifyPublicDomain)

```bash
control_tools.py ms-modify-public-domain --id <instance-id> --enable true/false --endpoint-type <type> [--eip-id <eip-id>]
```

Allowed `--endpoint-type` values:
- `MILVUS_PRIVATE`, `MILVUS_PUBLIC`, `MILVUS_INNER`
- `MILVUS_SERVERLESS_PRIVATE`, `MILVUS_SERVERLESS_PUBLIC`

EIP behavior:
- If enabling (`--enable true`) and `--eip-id` is omitted, the CLI can auto-allocate an EIP via VPC, but you must provide:
  - `--eip-bandwidth <int>`
  - `--eip-billing-type <str>` (Allowed: `PrePaid`, `PostPaid`, `PostPaidByTraffic`)
- Use `--eip-auto-reuse true` to search for an existing `Available` (unbound) EIP before allocating a new one. This avoids quota issues.
- Disabling (`--enable false`) never auto-releases any EIP.

### ms-modify-endpoint-allow-group (MSModifyEndpointAllowGroup)

```bash
control_tools.py ms-modify-endpoint-allow-group --id <instance-id> --endpoint-type <type> --allow-groups-json '<json>'
```

Example allow-group JSON:

```bash
control_tools.py ms-modify-endpoint-allow-group \\
  --id <instance-id> \\
  --endpoint-type MILVUS_SERVERLESS_PUBLIC \\
  --allow-groups-json '[{\"group_name\":\"default\",\"list\":[\"1.2.3.4/32\",\"10.0.0.0/8\"]}]'
```

---

## Regular (Non-MS) Public Domain

### modify-public-domain (ModifyPublicDomain)

```bash
control_tools.py modify-public-domain --id <instance-id> --enable true/false --endpoint-type <type> [--eip-id <eip-id>]
```

Allowed `--endpoint-type` values:
- `MILVUS_PRIVATE`, `MILVUS_PUBLIC`, `MILVUS_INNER`

EIP behavior:
- If enabling (`--enable true`) and `--eip-id` is omitted, the CLI can auto-allocate an EIP via VPC, but you must provide:
  - `--eip-bandwidth <int>`
  - `--eip-billing-type <int>`
- Disabling (`--enable false`) never auto-releases any EIP.

### modify-endpoint-allow-group (ModifyEndpointAllowGroup)

```bash
control_tools.py modify-endpoint-allow-group --id <instance-id> --endpoint-type <type> --allow-groups-json '<json>'
```

Example allow-group JSON:

```bash
control_tools.py modify-endpoint-allow-group \\
  --id <instance-id> \\
  --endpoint-type MILVUS_PUBLIC \\
  --allow-groups-json '[{\"group_name\":\"default\",\"list\":[\"1.2.3.4/32\",\"10.0.0.0/8\"]}]'
```

---

## EIP (VPC) Commands

These commands manage EIP resources in VPC. Use them to inspect or pre-provision EIPs for public domain binding.

### eip-list (DescribeEipAddresses)

```bash
control_tools.py eip-list [--page-number <n>] [--page-size <n>] [--allocation-id <id>] [--eip <ip>] [--status <status>] [--project-name <name>]
```

### eip-detail (DescribeEipAddressAttributes)

```bash
control_tools.py eip-detail --allocation-id <id>
```

### eip-allocate (AllocateEipAddress)

```bash
control_tools.py eip-allocate --eip-bandwidth <int> --eip-billing-type <int> [--eip-isp <isp>] [--eip-name <name>] [--eip-description <desc>] [--eip-project-name <name>]
```

### eip-release (ReleaseEipAddress)

**Destructive. Requires explicit confirmation.**

```bash
control_tools.py eip-release --allocation-id <id> --confirm <id>
```
