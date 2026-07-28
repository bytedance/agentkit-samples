---
name: agentkit-hybrid-cloud-demo
description: Deploy, update, validate, and troubleshoot the AgentKit hybrid-cloud customer-service demo in this directory. Use when a user asks an AI coding agent to follow the README, deploy or update the demo, configure OpenAPI/Runtime/Knowledge/Memory/Sandbox/MCP/Skills/A2A, run customer-view validation, or record manual platform steps and failures.
---

# AgentKit Hybrid Cloud Demo

## Operating contract

1. Treat `README.md` as the customer-facing source of truth. Read the requested step and its linked document before acting.
2. Start from a clean validation directory. Preserve unrelated or pre-existing changes.
3. Execute steps in README order unless the user names one specific step. Do not silently skip a failed prerequisite.
4. Prefer the repository scripts over reconstructed commands:
   - Human-guided Base Runtime: `scripts/deploy_interactive.sh`
   - Non-interactive/CI Base Runtime: `scripts/deploy_hybrid.sh`
   - Resource association and release: `scripts/bootstrap_platform.py`
   - Knowledge/Memory proof: `scripts/verify_knowledge_memory.py`
   - Local guide and Chat UI: `scripts/run_local_ui.sh`
5. Perform safe read-only discovery automatically. Stop for genuine human-only actions such as hosts/DNS changes requiring administrator access, console account switching, model selection, uploading documents, obtaining temporary credentials, or production authorization changes.
6. Never write or print AK/SK, passwords, Runtime API Keys, model keys, temporary Registry tokens, Bearer tokens, or injected component credentials. Use placeholders in docs and commands.
7. After each step, report:
   - action and evidence;
   - pass, fail, partial, or blocked;
   - required human action;
   - README/FAQ defect found and the minimal proposed update.

## Mandatory safety and validation

- Verify `${AGENTKIT_OPENAPI_SCHEME:-http}://${AGENTKIT_OPENAPI_HOST}/ping` before deployment. This delivered POC defaults to HTTP; honor an explicit HTTPS setting with normal certificate validation. Never make `curl -k` the customer solution, and clearly distinguish the POC HTTP default from a production HTTPS requirement.
- Default customer deployment to `live`. For the sample's default Ark profile, require `MODEL_AGENT_API_KEY` and resolve the documented default Model Name/API Base. For a custom or real environment, honor explicit API Base, Model Name, and API Key overrides. Inject all three resolved values during launch, fail clearly when the key is absent, and never silently downgrade to demo. Use `AGENTKIT_DEPLOY_MODE=demo` only when the user explicitly authorizes an infrastructure-only fallback, and label that result incomplete.
- Keep model values out of the public config, project `.env`, Git, Docker build context, logs, and prompts. Use the deployment script's transient `0600` config or a platform Runtime Secret.
- Do not manually `docker pull` or proactively require `docker login`. If `agentkit launch` actually returns `token expired`, `unauthorized`, `invalid token claims`, or `authentication required`, stop and explicitly guide the user to refresh the target Registry's temporary `docker login`, confirm `Login Succeeded`, and rerun launch. This manual login is the required recovery path after an observed authentication failure, not a prohibited action. Never ask the user to paste the token into chat or save it in the repository.
- Never silently reuse a global Region for Runtime creation. Require the user to confirm `VOLCENGINE_REGION`, preferably through `scripts/deploy_interactive.sh`; show any detected global value only as a hint.
- Before launch, detect an exact same-name Runtime in the confirmed Region. In an interactive session, ask whether to update that Runtime or enter a new unique name; check the new name before creation and never silently overwrite. In automation, require an explicit `AGENTKIT_RUNTIME_ID` or reuse authorization. Persist only the non-secret `launch_types.hybrid.runtime_name` and `runtime_id` after a successful launch so later runs update rather than hit `InvalidParameter.DuplicateName`; keep endpoint and API/model keys transient.
- Treat `scripts/deploy_interactive.sh` as the single first-deployment entry point for a human. It may reuse a confirmed existing CLI target or collect OpenAPI scheme/host, hidden AK/SK, Region, model profile, and hidden model key interactively. Do not require users to prepare exports or an Agent Prompt for this first deployment. After it succeeds, route later validation and capability work through the roadmap Prompts, which load this project Skill.
- Build and publish `linux/amd64`, including from Apple Silicon.
- Treat `agentkit launch` output as insufficient proof. Require Runtime `Ready`, service `RUNNING`, health `Healthy`, and a successful `/invoke`.
- Distinguish connection transport from Agent data mode: `transport=remote, mode=demo` proves the remote Runtime was called but still uses the deterministic demo; only `transport=remote, mode=live` proves the live Agent data plane handled the request.
- After `runtime update`, run `runtime release` and wait for `Ready/Healthy`.
- List platform resources with explicitly limited non-sensitive fields. Never dump full Tool JSON or environment variables.
- Do not delete, destroy, reset, or overwrite resources unless the user explicitly authorizes the exact target.

## Step routing

### Base Runtime

Read `docs/steps/00-runtime.md` and `docs/runtime_deployment.md`. Validate local dependencies, Docker, environment-specific OpenAPI, AK/SK availability, Region, model configuration presence, deployment config, image architecture, live launch, health, invoke, and platform LLM Trace. For an interactive customer session, use `scripts/deploy_interactive.sh`; use `scripts/deploy_hybrid.sh` only when the required values are already supplied for automation. After deployment, guide the user to obtain the target Runtime's own Endpoint/API Key, connect `/chat`, send a new request, and interpret local/remote plus demo/live evidence.

Use the repository's single uv-managed environment throughout: install uv with its official installer when absent, run `uv sync --frozen --extra dev`, and execute Python tools through `uv run`. Do not create a second venv or mix project dependencies with `pip install`.

### Step 1 — Knowledge

Read `docs/steps/01-knowledge.md`. Use the AgentKit CLI's read-only `knowledge list`
operation, which calls the configured platform API, and return only Knowledge ID, name,
status, and provider type. In the hybrid-cloud environment, the configured OpenAPI already
targets the hybrid-cloud Knowledge backend; a `Ready` Knowledge returned by that API is a
valid reuse candidate. AgentKit 0.5.5 exposes only the public-cloud
`VIKINGDB_KNOWLEDGE` CLI enum, while hybrid-cloud List/Get responses may legitimately
return an empty provider type. Never apply the VikingDB provider filter to hybrid-cloud
discovery or reject a resource because that field is empty. Reuse a matching published
Knowledge when possible. Otherwise guide the user through console Knowledge creation,
model choice, document upload, publication, and `Ready` check. Record the Knowledge ID
without exposing credentials.

### Step 2 — Memory

Read `docs/steps/02-memory.md`. Use the AgentKit CLI's read-only `memory list` operation
and return only Memory ID, name, status, and provider type. Reuse a matching `Ready`
`MEM0` Memory when possible; do not infer existence from Runtime association alone.
For reliable cross-session proof, also require a managed PostgreSQL session component.
Creating/importing it in **AgentKit → 会话管理 (Session)** is only preparation: guide the
user to **目标 Runtime → 关联组件 → 会话资源** to bind it, verify that section is no longer
empty, then release. The current Runtime CLI cannot associate that component; never
inspect its injected database credentials.
Otherwise guide the user through required Embedding/LLM selections and strategies. If CLI
creation cannot express required model settings, stop retrying and use the console path.

### Step 3 — Runtime association

Read `docs/steps/03-runtime-association.md`. Use `scripts/bootstrap_platform.py` with the confirmed resource IDs. Release the Runtime and wait for `Ready/Healthy`; association UI alone is not proof.

### Step 4 — Knowledge and Memory proof

Read `docs/steps/04-knowledge-memory-validation.md`. Do not run the proof until both Knowledge and Memory exist and are Ready, both IDs and managed PostgreSQL session component are associated with the target Runtime, the Runtime has been released back to Ready/Healthy, and Runtime Endpoint/API Key are available from the Runtime call page. If a prerequisite is missing, route back to the immediately preceding creation or association step instead of treating the expected block as a new runtime defect. Use `scripts/verify_knowledge_memory_interactive.sh` so Endpoint/API Key are hidden inputs scoped to the child process, then require a unique Knowledge canary hit, same-user cross-session recall, and different-user isolation. A first cross-session read can trigger VeADK's previous-session save, so honor the script's bounded polling rather than treating a single early empty result as conclusive.

### Step 5 — Sandbox and MCP

Read `docs/steps/05-sandbox-mcp.md` and `docs/mcp_validation.md`. Distinguish AIO Sandbox
from the local fallback and platform MCP from the demo `/mcp`. Require real Runtime logs
or Trace evidence for tool execution.

For MCP, keep service transport, tool discovery, Toolset selection, Runtime association,
and live execution as separate evidence layers. First use the MCP service **调试** page's
**连接测试** with the API Key entered only in a user-visible hidden field. If it remains
pending or times out, stop at `MCP service transport/startup timeout`; `Ready` does not
prove the backend is listening, and neither `GetMCPTools` `NotFound` nor an empty Runtime
tool list proves that the target tool was not selected. Inspect redacted service logs for
startup/dependency cold start, Streamable HTTP path/protocol, DNS/egress, and auth failures.
In a multi-service Toolset, one timed-out service can abort or truncate aggregate discovery
and hide another service's tools; require every included service to pass connection testing,
or use a single-service Toolset for deterministic acceptance.
Only after connection succeeds may tool enumeration prove whether the exact tool is
present. Then confirm Toolset scope, release the Runtime, and require the requested tool,
the Runtime MCP-router Tool Span, and service discovery/`tools/call` evidence.

### Step 6 — Skills

Read `docs/steps/06-skills.md`. The demo's publishable business Skill is in the repository
shared directory `skills/customer-service-compliance/SKILL.md` (from this Demo directory:
`../../../skills/customer-service-compliance`). The default upload artifact is
`../../../skills/customer-service-compliance.zip`; validate it locally, then guide the
user to create/select a Skills Space and upload that ZIP in the console. Rebuild the ZIP
only after changing `SKILL.md`. Do not confuse it with `.agents/skills/agentkit-hybrid-cloud-demo`,
which is an Agent instruction rather than a platform Skill. Require a published Skill,
its Skills space ID, Runtime association, explicit `execute_skills`, and evidence for
metadata loading plus isolated Sandbox execution. Do not invent MinIO bucket configuration.
Configure the Skills Sandbox with `AGENTKIT_SKILL_HOST=<top-host>` and
`AGENTKIT_TOP_SCHEME=http`; it needs those values to locate the Skills Space through
the hybrid-cloud TOP. Configure Runtime `SKILL_SPACE_ID=<ss-...>` separately, using
`scripts/bootstrap_platform.py --skill-space-id` when automation is appropriate. That
script preserves existing Runtime environments in memory and never prints their values.
Then bind the Skills Sandbox in Runtime association; the association supplies the Tool
ID but does not replace `SKILL_SPACE_ID`. Never use partial `--envs-json`, because it
replaces the entire list and can delete the model API Key.
Run `scripts/verify_skills_interactive.sh --show-response` for the final Runtime proof.
It creates a unique `SKILL_CANARY_<id>` and accepts PASS only when the visible response
contains `customer-service-compliance`, `needs_confirmation`, and that exact code. Then
use the code's user/session values to locate the three required Trace/log evidences.

### Step 7 — A2A and identity

Read `docs/steps/07-a2a-identity-session.md` and `docs/a2a_agent_validation.md`. Deploy the separate deterministic data-analysis Runtime through `scripts/deploy_a2a_interactive.sh`; its first-run Runtime name is `hybrid-cloud-customer-service-a2a`, so it cannot select the main Runtime from the public template. It creates/updates only the A2A Runtime binding, injects `AGENT_APP_MODE=a2a_data_analyst` and does not require a model key. Do not manually create a same-image Runtime unless that script is unavailable. Current CLI support stops at Runtime deployment: the first A2A Space/AgentCard registration and any production authorization stay as console-confirmed actions. After registration, obtain the data Runtime API Key from its call page and the service address from the A2A Center, then use `scripts/configure_a2a_peer_interactive.sh`. That script confirms the main Runtime ID, safely merges only the A2A peer variables, preserves all existing environment values in memory, releases the main Runtime, and waits for `Ready`. Run `scripts/verify_a2a_interactive.sh --show-response` for final proof: it generates one `A2A_CANARY`, directly validates Card/message-send, then validates main Runtime delegation; require three PASS lines plus the main Runtime delegation Tool Span and data Runtime AgentCard GET/`POST /a2a` 200 logs with the same canary.

Do not require the operator to copy a capability ID from the A2A Center UI. That page may
show only the capability display name; its **JSON file** contains `skills[].id`.
`scripts/configure_a2a_peer_interactive.sh` must instead use the supplied service address
and hidden data-Runtime API Key to discover the AgentCard. It automatically selects one
capability and presents only discovered IDs when the Card contains several.

Keep A2A terminology separate from the AgentKit Skills Center. The A2A specification calls
the AgentCard capability array `skills`, and this demo retains
`A2A_DATA_AGENT_SKILL_ID` as a compatibility environment key, but its value is an
AgentCard `skills[].id` capability such as `complaint-trend-analysis`. In user-facing
instructions call it **AgentCard capability ID**. It is not a published Skills Center
Skill, `SKILL_SPACE_ID`, Skills ZIP, or Skills Sandbox association; never route an A2A
peer configuration through `execute_skills`.

Treat OAuth identity as a third, separate Runtime. Never change the primary API-Key
Runtime in place. Run `scripts/deploy_oauth_interactive.sh`; its first-run name is
`hybrid-cloud-customer-service-oauth`, and its independent `agentkit.oauth.yaml`
contains only non-secret `custom_jwt`, OIDC Discovery, and allowed Client ID settings.
The operator must confirm/create the user-pool OAuth Client in the console. Never request
or persist the Client Secret during deployment. After release, run
`scripts/verify_oauth_interactive.sh --show-response`; it obtains a short-lived token with
hidden Client credentials and immediately invokes the independent OAuth Runtime with
`Authorization: Bearer <token>`. Treat HTTP 200 plus a visible final response as the
default positive proof; do not invent a separate OAuth-service validation workflow.
Missing/malformed JWT rejection is an optional security demonstration enabled with
`--negative-checks`, not a prerequisite for the normal token-to-Runtime flow. The first
proof must be tool-free. Require OAuth Runtime Trace evidence with no Authorization/JWT
value. State clearly that client credentials prove application
identity only; end-user identity needs Authorization Code + PKCE, and gateway acceptance
does not prove `sub`/custom `tenant_id` propagation. Never reuse the inbound user JWT as a
Knowledge, MCP, Skills, or A2A downstream credential.

The current hybrid-cloud POC user-pool host may be HTTP-only while AgentKit CLI 0.5.5
locally validates Discovery as HTTPS-only. When the operator explicitly selects HTTP,
allow `deploy_oauth_interactive.sh` to enable its process-local compatibility wrapper.
Never apply that relaxation to the primary Runtime or a formal environment; formal
environments must use HTTPS. If deployment returns immediately after the OpenAPI `/ping`
line and no OAuth Runtime exists, diagnose the local config/Region validation path before
claiming that Runtime creation failed.

Treat the main customer-service Runtime, data-analysis Runtime, and OAuth Runtime as
separate identities. PostgreSQL session and cross-session Memory evidence belong to
steps 02–04 and must not be repeated here.

### Step 8 — Evaluation and observability

Read `docs/steps/08-evaluation-observability.md` and `docs/evaluation_and_observability.md`. The CLI has no
evaluation-set/evaluator/experiment creation commands, so explicitly guide the user through console creation:
import `evaluation/hybrid_customer_service_runtime_core_v1.csv`, check its `input` and `reference_output`
fields and 4 rows, submit an immutable version, then create a **Code-only release-gate experiment**. In its Code
custom evaluator, the left execution pane receives the full `evaluation/runtime_deterministic_checks_v1.py` (the
platform injects `EvalOutput`; never add `from evaluator import ...`); the
right-side `turn` editor accepts exactly one complete JSON, so fully replace (never append) the default Taiwan test
with one JSON under `evaluation/code_evaluator_test_data/`, run it, then fully replace it with the next; require a
top-level `score=1` before saving. The evaluator must return `EvalOutput(score=..., reason=...)`, not a
`metrics`/`confusion_label` structure. Apply the LLM "正确性" template only in a separate quality-observation experiment: it can
judge platform-saved thought content rather than the final answer, so it must not turn this four-case release gate red.
Create the uniquely named Code experiment against the confirmed main Runtime at concurrency 1. Do not count evaluator
"trial run" as Runtime proof; require 4 `actual_output` rows and Code 4/4 from the experiment. Require versioned evaluation cases,
deterministic checks, a released observable Runtime, and platform Trace evidence that can locate failures to the model
or tool Span.

## Completion

Run relevant tests and static checks after code or documentation changes. Store customer
validation records in a Git-independent sibling workspace (recommended:
`<repo-parent>/agentkit-hybrid-cloud-validation/<date>/`), never as
`docs/*_validation.md` in the Demo source tree. Record only non-sensitive evidence,
human actions, and resulting README/FAQ/Skill improvements. Finish with the exact next
customer action, not merely a command transcript.
