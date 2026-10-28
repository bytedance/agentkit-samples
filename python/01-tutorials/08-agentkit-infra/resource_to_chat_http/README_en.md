# Harness Infra: From Resource Creation to a Real Conversation

This pure HTTP example covers the complete Harness Infra onboarding flow:

1. Call the control-plane TOP endpoint with account AK/SK.
2. Create or reuse an Endpoint.
3. Create a Cloud Environment and wait for its Cloud Sandbox.
4. Create a Harness.
5. Create a managed `SERVERLESS_PG` SessionStore and wait for `Ready`.
6. Create a RuntimeTemplate associated with that SessionStore, preparing
   `AgentKitDefaultRuntimeAccess` within this stage.
7. Create an Environment API Key and write its ID and plaintext to `config.yaml`.
8. Create a Session through the Endpoint `BaseUrl` and persist its information
   to `config.yaml`.
9. Send a user message and verify a real model response.
10. Repeat conversations as needed, then delete the Key, RuntimeTemplate,
    SessionStore, and Environment and archive the Harness.

The account-level Endpoint is retained.

## Files

| File | Purpose |
| --- | --- |
| `01_create_resources.py` | Create control-plane resources, the Environment API Key, and Session |
| `02_invoke_session_http.py` | Read the Session from YAML and call the Event data plane over HTTP |
| `02_invoke_session_ant_sdk.py` | Invoke the existing Session with the Anthropic SDK |
| `02_invoke_session_ark_sdk.py` | Invoke the existing Session with the Ark SDK |
| `02_invoke_session.sh` | Fixed curl send script with empty connection settings |
| `02_sse_session.sh` | Fixed curl SSE script with empty connection settings |
| `03_cleanup_resources.py` | Clean up the Session and control-plane resources |
| [`../config.yaml.example`](../config.yaml.example) | Shared redacted configuration template |
| `../config.yaml` | Default shared Environment, Harness, RuntimeTemplate, and account configuration |
| `_clients.py` | TOP HMAC-SHA256 and data-plane REST clients |
| `_common.py` | Redacted output, state, and polling |
| `_workflow.py` | Deterministic lifecycle orchestration |
| `tests/test_flow.py` | Offline protocol tests |

## Control Plane and Data Plane

| Plane | Endpoint | Authentication | Field convention |
| --- | --- | --- | --- |
| Control | `https://open.volcengineapi.com/` | Account AK/SK signed with the published Service and Region | PascalCase; lists use `Items/NextToken` |
| Data | The Endpoint `BaseUrl` | The Environment Key returned once by `CreateAPIKey`, sent as `x-api-key` | Session/Event REST uses snake_case |
| Model credential | Resolved by the Runtime | The Ark API Key **Name** is sent as `x-ark-key-name` | No model key plaintext is sent by this client |

Account credentials, the Environment Key, and the Ark model key are distinct and
cannot replace one another.

## Prerequisites

- The account has access to the published Harness Infra Service.
- The account can create Endpoint, Environment, Harness, SessionStore,
  RuntimeTemplate, and API Key resources, and has Serverless PostgreSQL enabled.
- An Ark API Key already exists and its **Name** is known. Do not use its plaintext,
  SID, or internal ID as the Name.
- The account can query and create IAM Roles and attach system policies. The
  example reuses or creates `AgentKitDefaultRuntimeAccess` and attaches
  `AgentKitDefaultRuntimeAccess` when it creates the role.
- The selected model ID is available to that Ark API Key.

## Install

```bash
uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
cp -n ../config.yaml.example ../config.yaml
```

Every script first honors `HARNESS_INFRA_CONFIG`, then looks for the shared
`08-harness-infra/config.yaml` one directory above. If absent, it falls back to
the existing `resource_to_chat_http/config.yaml`. Default paths are relative to
the scripts, independent of the working directory. Fill in the copied
`../config.yaml` before the first run. Runtime values are written back to the
selected config, never the template. Git ignores config files; do not commit or share them.

## Configuration

Use `config.yaml` for the Harness system prompt, model, AgentLoop, Tools, Skills,
MCP Servers, SessionStore, Environment and RuntimeTemplate resource specifications, Session
title, prompt and response checks, and the Volcengine account AK/SK and Region.
Explicit model CLI options and `--agent-loop` override YAML.
Fields marked as required in the template must be filled in. Review fields
marked for the target environment. Never fill in `environment.env_api_key` or
the Session `id`, `name`, and `endpoint_base_url`; steps 01 and 03 manage them.
`harness.model.project_name` is retained for Ark project configuration; the
default Ark project is usually named `default`.

`agent_loop` belongs to the Harness. RuntimeTemplate accepts `resources`,
`image_url`, `envs`, and `runtime`. Environment uses `type: Cloud` plus
`cpu_milli` and `memory_mb`. The sample always creates a managed `SERVERLESS_PG`
SessionStore. Public networking needs no additional values; private networking
requires `use_private_network: true`, `vpc_id`, and exactly one `subnet_ids`
entry. These levels match the control API request bodies.

Before any network request or state write, the scripts validate AK/SK, model Key
Name, model ID, and URL. Missing values, example placeholders, credentials with
whitespace, and invalid Key Names stop immediately.

Use an isolated state file:

```bash
export HARNESS_INFRA_STATE="/tmp/harness-infra-chat-$(date +%s).json"
```

The state file is created with mode `0600` and stores only IDs, names, statuses,
and idempotency tokens. Step 01 writes the Environment API Key ID and plaintext
to `config.yaml` under `environment.env_api_key`, then writes the Session ID,
name, and data-plane URL under `session`. Step 02 reads these values directly
and can run repeated model turns in the same Session without calling the control
plane. Step 03 deletes the Session and cloud Key and clears the runtime YAML
fields. Do not commit or share this file while plaintext is present.

## 1. Create Resources

```bash
python 01_create_resources.py \
  --prefix harness-chat \
  --agent-loop adk
```

The script:

- Lists Endpoints and creates one only when none exists.
- Creates a Cloud Environment using the YAML resource specification.
- Waits for the Cloud Environment's Sandbox to become ready.
- Creates a Harness with the configured model, AgentLoop, System, Tools, Skills,
  and MCP Servers.
- Creates a managed Serverless PostgreSQL SessionStore and polls
  `GetSessionStore` until `Ready`. State stores only its ID and public metadata,
  never database credentials.
- Prepares the Runtime Role (reuse, or create and attach the Runtime policy),
  then creates a RuntimeTemplate from the configured resources, image, environment
  variables, and Runtime object, passes `SessionStoreId`, then waits for `Ready`.
  AppO injects `DATABASE_POSTGRESQL_*` while creating the Runtime so the
  AgentLoop persists Sessions.
- Creates the Environment API Key bound to the Environment and Endpoint and
  writes its ID and one-time plaintext to `config.yaml`.
- Creates the Session and writes its ID, name, and Endpoint `BaseUrl` to
  `config.yaml`.
- Fills `ENDPOINT`, `SESSION_ID`, and `ENV_API_KEY` in the fixed repository scripts
  `02_invoke_session.sh` and `02_sse_session.sh`, using the actual Endpoint,
  Session ID, and `environment.env_api_key.value`. Only those three assignments
  change; custom request bodies and other shell code are preserved. Repository
  defaults are empty. Filled scripts have mode `0700`; do not commit filled credentials.

Run `./02_invoke_session.sh` to send the financial-report PPT request, then
`./02_sse_session.sh` to replay and subscribe to raw SSE events with `curl -N`.
The POST response only acknowledges receipt. To resume without sending again,
use `./02_sse_session.sh 50` for events after sequence 50. Ctrl+C cleans up the
background curl process. Stream closure does not imply completion; check for
`session.status_idle` with `end_turn` and reconnect using the last sequence when
needed. Successful Session creation updates only connection settings; it does not
regenerate the scripts. `--dry-run` leaves them unchanged. Empty settings cause
the scripts to stop before sending any request.

Both fixed scripts live in `resource_to_chat_http`, whether using the shared,
legacy, or custom config. Creation prints their full paths.

If the resources already exist and YAML contains the Session and Key, fill the
connection settings without recreating resources:

```bash
python -c "from _curl import configure_session_curl_scripts; configure_session_curl_scripts()"
```

Select an Endpoint explicitly when the account has more than one:

```bash
python 01_create_resources.py --endpoint-id ep_example
```

`--dry-run` performs no network or state writes.

## 2. Run a Real Conversation

The default prompt requires real `write`, `edit`, `read`, `grep`, `glob`, and
`bash` calls and computes `17 × 23` from a sandbox file. The scripts print each
tool's success or failure and result summary in event order. No fixed answer or
tool set is required by default, so edit `session.prompt` to run other scenarios:

```bash
python 02_invoke_session_http.py
```

Custom verification:

```bash
python 02_invoke_session_http.py \
  --prompt 'Reply with only: HARNESS_CHAT_OK' \
  --expected-substring 'HARNESS_CHAT_OK'
```

`--expected-substring` is an optional per-invocation assertion and does not need
to be stored in YAML. Strict E2E configurations may still add the optional
`expected_substring` and `verify_sandbox_tools` fields; ordinary tutorial calls
do not need them.

The script:

1. Reads the Session, Endpoint `BaseUrl`, prompt, and Environment API Key created
   by step 01 from `config.yaml`.
2. Sends a `user.message` with a new event ID.
3. Reads persistent events incrementally by sequence.
4. Associates each `agent.tool_use` with its `tool_result` by call ID and prints
   a prominent single-line summary limited to 500 characters, followed by the
   complete redacted event JSON in a separate bordered panel. `--json` preserves
   the complete event in `raw_result`.
5. Succeeds only after an `agent.message` followed by
   `session.status_idle` with `stop_reason.type=end_turn`.

An HTTP 200, accepted Event, or arbitrary idle status is not a completed model
turn.
Until step 03 runs, any step 02 script may be executed multiple times. Each
invocation reuses the YAML Session and uses a new Event ID.

Run the same Harness data-plane flow with the official Anthropic SDK:

```bash
python 02_invoke_session_ant_sdk.py
```

The Ark SDK generic request methods can run the same Harness Session/Event data
plane flow. This script uses the Endpoint `BaseUrl` and Environment API Key; it
does not call Ark Responses directly with account AK/SK:

```bash
python 02_invoke_session_ark_sdk.py
```

If step 01 is terminated after `CreateAPIKey` returns but before YAML is
written, the plaintext cannot be recovered. Run step 03 to delete the old Key
by its state ID before starting a new run.

## 3. Clean Up

```bash
python 03_cleanup_resources.py
```

Cleanup order:

1. Delete any remaining Session, then delete the Environment API Key.
2. Delete RuntimeTemplate and wait for Get to return 404.
3. Delete SessionStore and wait for Get to return 404.
4. Internally clean up the Cloud Sandbox, then delete Environment.
5. Archive Harness and retain Endpoint.
6. Before exit, whether cleanup succeeds or fails, clear the API Key and Session runtime fields from YAML and `ENDPOINT`, `SESSION_ID`, and `ENV_API_KEY` from both `02_*.sh` scripts. Preserve all other script content. `--dry-run` leaves files unchanged.

Cleanup uses the YAML Key when an interrupted Session remains active.

## Common Stops

| Symptom | Action |
| --- | --- |
| `CreateEndpoint` returns 409 | List and reuse the existing Endpoint; this example handles the single-Endpoint case automatically |
| `CreateAPIKey` reports `The number of the APIKey has exceeded the quota` | Raise the APIG `api_key-per-consumer` quota, or have resource owners remove confirmed unused Keys; never delete unknown Keys from other Environments |
| RuntimeTemplate remains `Building` | Continue Get with the original ID; do not create another template with a new token |
| SessionStore remains `Creating` | Call `GetSessionStore` with the ID in state; check Serverless PG quota, account billing, and VPC/subnet settings |
| `x-ark-key-name` resolves zero or multiple Ark Keys | Use the unique complete Name in the same account, region, and project, not plaintext, SID, or a prefix |
| Session returns `requires_action` | This basic example does not process client tool confirmation; use a tool-free Harness or implement the required protocol |
| Environment deletion conflicts | Delete the Session and let cleanup finish the Cloud Sandbox first |

## Output and Timeouts

- Script 01 has seven steps: prepare Endpoint → create Environment and wait for Cloud Sandbox readiness → create Harness → create SessionStore and wait for readiness → create RuntimeTemplate (including IAM Role preparation) → create API Key → create Session. State initialization is silent. The final resource summary and invocation command are not numbered as a creation step. `--dry-run` follows the same order.
- Default output numbers creation, chat, and cleanup steps (`1, 2, 3…`). Each step keeps the resource name (when available), ID, core parameters, and status under one heading. Questions and answers use Chinese labels (`问 / 答`). Final summaries list names, IDs, and statuses without repeating parameters.
- Reused, deleted, and skipped resources also include their identifiers; Sessions include their title. Older state files reuse saved names without inventing missing metadata. API Keys show only names, IDs, and bindings. `--dry-run` lists numbered actions and explicitly marks names and IDs as not yet obtained.
- Creation requests (Endpoint, Environment, Harness, RuntimeTemplate, API Key, and Session), model conversations, and deletion waits use a single-line spinner in a terminal, then print the result once the target status (such as Ready) is reached. Redirected output and `--json` only log status changes. JSON events remain redacted and include a `step` field for numbered steps.
- Internal Cloud Sandbox resource IDs, revisions, and convergence generations are
  no longer printed or included in summaries.
- All three `02_` scripts (HTTP, Anthropic SDK, and Ark SDK) show the prompt before execution and finish with a result card containing the Session, turn completion status, successful tools, enabled checks, and the original agent reply. Elapsed time is currently hidden. Each tool step highlights a readable summary under `↳ 工具输出`, followed by a dim bordered `原始事件 · JSON` panel. Line breaks in summaries display as `\n`; long lines wrap only when needed to fit the terminal. Disabled tool-coverage and reply-text checks are explicitly labeled; `TOOL USE VERIFIED 391` remains the original agent reply.
- Script 03 shows Session / API Key checks, RuntimeTemplate deletion, Environment
  deletion, Harness archival, and completion. Missing or already cleaned
  resources are explicitly skipped; the Endpoint is retained.
- `HARNESS_INFRA_HTTP_TIMEOUT_SECONDS`: control request timeout, default 60.
- `HARNESS_INFRA_DATA_TIMEOUT_SECONDS`: data request timeout, default 60.
- `HARNESS_INFRA_WAIT_TIMEOUT_SECONDS`: asynchronous wait timeout, default 900.
- `HARNESS_INFRA_POLL_INTERVAL_SECONDS`: polling interval, default 5.
- `HARNESS_INFRA_HTTP_RETRIES`: automatic 429/503 retries, default 2.

Automatic and manual retries must preserve the exact body and idempotency token.

## Offline Verification

```bash
uv run --with-requirements requirements.txt \
  python -m unittest discover -s tests -v

uv run --with 'ruff==0.11.12' ruff check .
uv run --with 'ruff==0.11.12' ruff format --check .
```

Tests cover TOP signing and PascalCase bodies, resource convergence, Endpoint path
prefixes, Anthropic SDK Session/Event request generation, both authentication
headers, persistent Event completion, cleanup ordering, and the no-secret state
boundary.

## Contract Sources

- Harness Infra API guide: from resource creation to conversation
- akx `docs/harness-infra/api/`
- akx `docs/harness-infra/control-data-plane.md`
- API Version `2025-10-30`

Documentation, local tests, and a live deployment are separate evidence. Published
Actions, default images, Runtime role permissions, and model access must be
verified against the target environment.
