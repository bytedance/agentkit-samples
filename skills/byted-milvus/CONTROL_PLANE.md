# Control Plane - Cluster Management

Use this guide for regular and serverless Milvus control-plane operations via `control.py`: provision, inspect, scale, expose, and delete.

## When to use this document

Use `control.py` goal-based commands when the user asks to:
- Discover provisioning options (VPC/subnet/spec/version)
- Create or delete instances
- Check instance status
- Scale regular instances
- Enable or disable public endpoints

## Quick start

Goal-based command template:
`{baseDir}/venv/bin/python {baseDir}/scripts/control.py <command>`

Goal-based commands:
- `provision-info`: Fetch VPCs, subnets, specs, and versions for regular Milvus
- `provision`: Create a regular instance and poll until `Running`
- `status`: Fetch regular instance status, endpoints, and spec config
- `scale`: Scale one regular node type and poll until `Running`
- `enable-public`: Enable/disable a regular public endpoint, optionally auto-allocating or auto-reusing EIP and setting allow-groups
- `deprovision`: Delete a regular instance; requires exact-match `--confirm`
- `ms-provision-info`: Fetch VPCs, subnets, and supported versions for serverless
- `ms-provision`: Create a serverless instance and poll until `Running`
- `ms-enable-public`: Enable/disable a serverless public endpoint, optionally auto-allocating or auto-reusing EIP and setting allow-groups
- `ms-deprovision`: Delete a serverless instance; requires exact-match `--confirm`

## Command output handling

All goal-based commands return:

```json
{
  "status": "success|error|timeout",
  "goal": "<command>",
  "data": { "...": "..." },
  "steps_completed": ["step1", "step2"]
}
```

Validation rule after each command:
- If `status == "error"`, stop and surface the error.
- If `status == "timeout"`, follow the **Timeout Recovery** rules below.
- If `status == "success"`, continue to the next workflow step.

## Timeout Recovery

A `timeout` status means the CLI stopped polling, but the operation is likely still in-progress on the Volcano Engine side. When a timeout occurs, follow these rules:

1. **Analyze `steps_completed`**:
   - If the main mutation step (e.g., `create_instance`, `modify_public_domain`, `scale_node`) is in the list, the request was successfully sent. **NEVER** re-run the same mutation command immediately, as it may result in redundant resources or quota errors.
2. **Observe with Passive Commands**:
   - Use `status --id <id>` (regular) or `ms-detail --id <id>` (serverless) to observe the current state without re-triggering the mutation.
3. **Handle Transitional States**:
   - If the instance is in a state like `Creating`, `Updating`, `Scaling`, or `Releasing`, wait 30-60 seconds and check the status again. 
   - Inform the user that the operation is still running and provide the current status.
4. **Resuming Work**:
   - If the goal was to reach `Running` and the instance has finally reached it, you can proceed to the next step of your checklist.

## Intent routing

Use this mapping for user intent:
- "What versions/specs/VPCs are available?" -> `provision-info` or `ms-provision-info`
- "Create a cluster" -> provisioning workflow
- "List my instances" -> `control.py list` or `control.py ms-list`
- "Show cluster details" -> `status --id <id>` (regular) or `control.py ms-detail --id <id>` (serverless)
- "Scale node type" -> scaling workflow (regular only)
- "Expose endpoint publicly" -> `enable-public` (regular) or `ms-enable-public` (serverless)
- "Delete instance" -> deletion workflow (explicit confirmation required)

## Regular provisioning workflow

Copy and track this checklist:

```text
Provisioning Progress:
- [ ] Step 1: Fetch provisioning options (`control.py provision-info`)
- [ ] Step 2: Present options and confirm user choices
- [ ] Step 3: Collect required inputs (name/password/capacity)
- [ ] Step 4: Execute create (`control.py provision ...`)
- [ ] Step 5: Validate terminal state (`Running` or follow-up required)
- [ ] Step 6: (Optional) Enable public endpoint
```

Step details:

1. Fetch options:
   `control.py provision-info`
2. Present and confirm: VPC, subnet, spec, version.
3. Collect inputs:
   - `name`
   - `cpu`, `mem`
   - strong admin `password`
   - optional: `version`, `cu-type`, `ha`
4. Create:

```bash
control.py provision --name <name> --vpc-id <vpc-id> --subnet-id <subnet-id> --cpu <cores> --mem <gb> --password <password> [--version <value>] [--cu-type <class>] [--ha true/false]
```

5. Validate result:
   - `status == success`: confirm instance is `Running`.
   - `status == timeout`: tell user provisioning is still running; re-check with:
     `control.py status --id <instance-id>`.
6. Optional public endpoint:

```bash
control.py enable-public --id <instance-id> --enable true --endpoint-type MILVUS_PUBLIC [--allow-groups-json '<json>'] [--eip-id <id>] [--eip-auto-reuse true/false]
```

If `--eip-id` is omitted:
- Provide `--eip-bandwidth` and `--eip-billing-type` (allowed: `PrePaid`, `PostPaid`, `PostPaidByTraffic`) for auto-allocation.
- Set `--eip-auto-reuse true` to automatically find and use an existing unbinded (`Available`) EIP in the region instead of allocating a new one. This is recommended to avoid billing and quota issues.
Validate endpoint by checking `detail_after` or rerunning:
`control.py status --id <instance-id>`, then confirm `endpoint_list` contains:
- `type: "MILVUS_PUBLIC"`
- non-null `eip`

Version note:
- Always prefer values returned by `provision-info`. Do not rely on defaults.

Spec resolution note:
- The API requires a `ResourceSpecName` per node type. Different node types use different spec families:
  - META_NODE, PROXY_NODE, DATA_NODE → `*_service_performance`
  - INDEX_NODE → `*_index_performance` (minimum 4 CPU)
  - QUERY_NODE → `*_compute_performance` (minimum 4 CPU)
- `control.py provision` auto-fetches V2 specs and resolves the best match per node type. If the requested cpu/mem is below the minimum for INDEX_NODE or QUERY_NODE, it auto-selects the smallest allowed spec.
- Override with `--spec-name` only if all node types share the same spec (rare).

## Regular deletion workflow (required)

Never skip confirmation.

```text
Deletion Progress:
- [ ] Step 1: Resolve target instance ID
- [ ] Step 2: Show current state (`control.py status`)
- [ ] Step 3: Request explicit confirmation phrase
- [ ] Step 4: Execute delete (`control.py deprovision`)
- [ ] Step 5: Validate delete result
```

1. Resolve instance ID:
   - If user gives only name, run `control.py list`, map name -> ID, then confirm ID.
2. Show current state:
   - `control.py status --id <instance-id>`
   - Summarize: `id`, `name`, `status`, endpoints.
3. Require unambiguous confirmation text:
   - `Yes, delete <instance-id>`
4. Delete:
   - `control.py deprovision --id <instance-id> --confirm <instance-id>`
5. Validate:
   - If `TaskIsRunning`, instruct user to retry after instance returns to `Running`.
   - If other error, stop and surface details.

## Regular scaling workflow

Run one scaling operation at a time.

```text
Scaling Progress:
- [ ] Step 1: Verify instance is `Running`
- [ ] Step 2: Identify node type and target capacity
- [ ] Step 3: Validate constraints
- [ ] Step 4: Execute a single scale operation
- [ ] Step 5: Wait for `Running`
- [ ] Step 6: Repeat for remaining node types (sequential only)
```

1. Verify state:
   - `control.py status --id <instance-id>`
   - If `Scaling`, wait and retry.
2. Node types:
   - `QUERY_NODE`, `DATA_NODE`, `INDEX_NODE`, `PROXY_NODE`, `META_NODE`
3. Constraints:
   - `META_NODE`: single-instance mode supports up to `4C16G`; above this, require HA with at least 2 nodes.
   - `DATA_NODE`: if `NodeNumTooSmall`, split into two sequential operations (vertical first, then horizontal).
4. Execute:

```bash
control.py scale --id <instance-id> --type <node-type> --cpu <cores> --mem <gb> --count <nodes> [--cu-type PERFORMANCE/CAPACITY] [--ha true/false]
```

5. Validate:
   - Command must return to `Running` before next scale.

## Serverless workflows

Use `ms-*` goal-based commands for serverless operations.

Provisioning:
1. Run `control.py ms-provision-info`.
2. Confirm VPC/subnet/version inputs.
3. Create:

```bash
control.py ms-provision --name <name> --vpc-id <vpc-id> --subnet-id <subnet-id> --password <password> [--version V2_5] [--project-name default] [--delete-protect true/false]
```

Public endpoint (serverless):

```bash
control.py ms-enable-public --id <instance-id> --enable true --endpoint-type MILVUS_SERVERLESS_PUBLIC [--allow-groups-json '<json>'] [--eip-id <id>] [--eip-auto-reuse true/false]
```

Deletion:
1. Follow the same confirmation pattern as regular deletion.
2. Run:

```bash
control.py ms-deprovision --id <instance-id> --confirm <instance-id>
```

Inspection and listing:
- List: `control.py ms-list`
- Detail: `control.py ms-detail --id <instance-id>`

Public domain and allow-group changes:
- Prefer `control.py enable-public` (regular) or `control.py ms-enable-public` (serverless).

## Safety rules (MUST)

- MUST require explicit confirmation before any delete operation.
- MUST operate on instance ID, not name, for mutating operations.
- MUST validate command `status` after every mutating command.
- If a timeout occurs, MUST run a passive observation command (`status`/`ms-detail`) before taking further action.
- MUST run scaling sequentially; never run concurrent scaling operations on the same instance.
- MUST stop and report if command output is `error`.
