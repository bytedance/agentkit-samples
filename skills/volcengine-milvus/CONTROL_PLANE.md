# Control Plane — Cluster Management

## Contents

- Use cases and triggers
- Provisioning workflow (multi-step with checklist)
- Deletion workflow (required)
- Commands: list, create, delete, detail, scale, vpc, subnet, versions, specs

---

## Use Cases

**Querying infrastructure** ("what node sizes are available?", "what Milvus versions?"): Run `specs` and `versions`.

**Provisioning** ("create a milvus instance"): Follow the **Provisioning workflow** below.

**Listing instances** ("list my milvus instances"): Run `list`.

**Inspecting details** ("get details for my cluster"): Run `detail --id <id>`.

**Scaling** ("scale up my proxy nodes"): Get instance ID → determine node type → ask for CPU/Memory/Count → run `scale`.

**Deleting** ("delete milvus instance"): Follow the **Deletion workflow** below. **MUST require explicit user confirmation. Do not execute delete without it.** If `TaskIsRunning` error, inform user to retry later.

---

## Provisioning Workflow

Copy this checklist and track progress:

```
Provisioning Progress:
- [ ] Step 1: Fetch VPCs (control.py vpc)
- [ ] Step 2: Fetch subnets (control.py subnet --vpc-id <id>)
- [ ] Step 3: Fetch specs (control.py specs)
- [ ] Step 4: Present options and get user choices
- [ ] Step 5: Get instance name and password from user
- [ ] Step 6: Create instance (control.py create ...)
- [ ] Step 7: Verify creation (control.py detail --id <id>)
```

**Step 1**: `control.py vpc` — fetch available VPCs.

**Step 2**: `control.py subnet --vpc-id <vpc-id>` — fetch subnets for chosen VPC.

**Step 3**: `control.py specs` — fetch available node specifications.

**Step 4**: Present VPC, subnet, and spec options. Ask user to choose.

**Step 5**: Ask user for instance name, desired CPU/memory, and high-strength admin password.

**Step 6**: `control.py create --name <name> --vpc-id <vpc-id> --subnet-id <subnet-id> --cpu <cores> --mem <gb> --password <password> [--cu-type <class>]`

**Step 7**: `control.py detail --id <instance-id>` — verify the instance. If status is not `Running`, inform user it is still provisioning and check again later.

**After creation (required before data operations)**:
- Newly created instances may not have a public address by default. The SDK/CLI does not currently support binding/enabling public access.
- If you need to run data-plane commands, the user must configure **Public Address** and **IP whitelist** in the Volcano Engine Milvus Web Console, then you can re-fetch the endpoint from `control.py detail` (look for `endpoint_list` entries with `type: "MILVUS_PUBLIC"` and non-null `eip`).

<Note>
**Version selection**: `control.py create` accepts `--version` (default: `V2_5`). Use `control.py versions` to list available values.
</Note>

---

## Deletion workflow (required)

Use this exact sequence for deletes:

```
Deletion Progress:
- [ ] Step 1: Confirm instance name or ID
- [ ] Step 2: Query and show instance details + current state (control.py detail)
- [ ] Step 3: Ask user to explicitly confirm deletion
- [ ] Step 4: Delete the instance (control.py delete)
```

**Step 1**: Confirm the target instance **name or ID**.
- If the user provides only a name (or is unsure), run `control.py list`, locate the matching instance, and confirm the **ID** you will use.

**Step 2**: Fetch and show details and current **status/state**:
- `control.py detail --id <instance-id>`
- Summarize at minimum: `id`, `name`, `status`, and endpoints if present (so the user can sanity-check the target).

**Step 3**: Ask for explicit confirmation.
- Require an unambiguous confirmation like: `Yes, delete <instance-id>` (or equivalent in the user's language).
- If the instance is not `Running`, tell the user you will wait/retry later (deletes may fail during other tasks).

**Step 4**: Execute the delete:
- `control.py delete --id <instance-id> --confirm <instance-id>`
- If API returns `TaskIsRunning`, inform the user to retry once the instance returns to `Running`.

---

## Scaling workflow (upgrade/downgrade)

Copy this checklist and track progress:

```
Scaling Progress:
- [ ] Step 1: Confirm instance is Running (control.py detail)
- [ ] Step 2: Identify node type(s) to change
- [ ] Step 3: Check constraints (see notes below)
- [ ] Step 4: Choose target CPU/mem and node count
- [ ] Step 5: Execute ONE scale operation (control.py scale ...)
- [ ] Step 6: Wait for Running, then verify spec_config (control.py detail)
- [ ] Step 7: Repeat sequentially for other node types (no concurrent operations)
```

**Step 1**: `control.py detail --id <instance-id>` — ensure status is `Running`. If `Scaling`, wait.

**Step 3**: Check constraints/pitfalls in the **scale** section below (keep them in mind before choosing CPU/mem/count).

**Step 4**: Ask for the target plan in one pass:
- Node type (`DATA_NODE`, `META_NODE`, etc.)
- Target CPU/memory
- Target node count
- Whether HA should be enabled/kept (`--ha`)

**Step 5**: Run exactly one operation at a time:

```bash
control.py scale --id <instance-id> --type <node-type> --cpu <cores> --mem <gb> --count <nodes> [--cu-type PERFORMANCE/CAPACITY] [--ha true/false]
```

---

## Output Format

All commands return JSON:

```json
{"status": "success", "data": { ... }}
```

On error:

```json
{"error": "API Exception", "details": "..."}
```

---

## Commands

All commands: `{baseDir}/venv/bin/python {baseDir}/scripts/control.py <command>`

### list

```bash
control.py list [--page-number <n>] [--page-size <n>]
```

Defaults: page 1, size 10. If `total > page_number * page_size`, fetch next page.

### create

```bash
control.py create --name <name> --vpc-id <vpc-id> --subnet-id <subnet-id> --cpu <cores> --mem <gb> --password <password> [--version <value>] [--cu-type PERFORMANCE/CAPACITY] [--ha true/false]
```

- `--cpu` and `--mem` are integers (e.g. `--cpu 4 --mem 16` = 4 cores, 16GB).
- `--cu-type` is optional. If omitted, the API typically defaults to `PERFORMANCE`.
- If user says specs in loose formats like `"2c8g"`, `"4核16G"`, `"4 CPU 16GB"`, extract the CPU and memory numbers.
- `--ha` defaults to **true**. Pass `--ha false` only if user explicitly wants non-HA.

### delete

**Low freedom — execute exactly as shown.**

```bash
control.py delete --id <instance-id>
```

If API returns `TaskIsRunning`, inform user to retry when status is `Running`.

### detail

```bash
control.py detail --id <instance-id>
```

### scale

```bash
control.py scale --id <instance-id> --type <node-type> --cpu <cores> --mem <gb> --count <nodes> [--cu-type PERFORMANCE/CAPACITY] [--ha true/false]
```

- `--cu-type` is optional. If omitted, the instance class remains unchanged.
- Only run scaling when instance status is `Running`. If status is `Scaling`, wait; concurrent operations may return `InstanceOperationForbidden`.
- Prefer one scaling dimension per operation: change **either** CPU/mem (vertical) **or** node count (horizontal), then wait for `Running` and verify via `detail`.
- Observed constraints/pitfalls:
  - `META_NODE` upgrades: single-instance mode supported up to **4C16G**. To go beyond, enable HA and use at least **2 nodes** (otherwise you may see `NodeNumTooSmall`).
  - `DATA_NODE` changes: if `NodeNumTooSmall` occurs during a downgrade/resize, split the plan into two sequential operations (vertical then horizontal, or vice versa) and retry after the instance returns to `Running`.

Node types: `QUERY_NODE`, `DATA_NODE`, `INDEX_NODE`, `PROXY_NODE`, `META_NODE`.

### vpc

```bash
control.py vpc
```

### subnet

```bash
control.py subnet --vpc-id <vpc-id>
```

### versions

```bash
control.py versions
```

### specs

```bash
control.py specs
```
