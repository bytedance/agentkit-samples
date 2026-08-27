"""AgentKit Runtime entry point.

The deterministic tools make the sample runnable without cloud credentials.
When model credentials are present, VeADK handles free-form dialogue and can
call the same tools. The business core remains directly testable.
"""

from __future__ import annotations

import json
import logging
import os

from demo_core import HybridCustomerService
from a2a_client import a2a_data_agent_configured, delegate_complaint_trend_analysis
from platform_knowledge import build_platform_knowledge, normalize_knowledge_tool_metadata
from platform_memory import build_platform_memory, normalize_memory_tool_metadata
from platform_mcp import build_platform_mcp_router
from platform_request_context import RequestAuthorizationMiddleware
from prompts import INSTRUCTION
from utils.config import Settings

settings = Settings.from_env()
service = HybridCustomerService(settings.effective_mode)
logger = logging.getLogger(__name__)


_POSTGRES_ENV_KEYS = (
    "DATABASE_POSTGRESQL_HOST",
    "DATABASE_POSTGRESQL_PORT",
    "DATABASE_POSTGRESQL_USER",
    "DATABASE_POSTGRESQL_PASSWORD",
    "DATABASE_POSTGRESQL_DATABASE",
)

# ``execute_skills`` starts a second, isolated Skills Sandbox process.  Only a
# small, explicit allow-list is forwarded to that process.  In particular we
# do not construct a MinIO endpoint, bucket name or static object-storage
# credentials in business code.  VeADK's hybrid-cloud implementation requests
# a temporary signed download URL from the AgentKit control plane instead.
_SKILLS_SANDBOX_CONTEXT_ENV_KEYS = (
    "CLOUD_PROVIDER",
    "VOLCENGINE_ACCESS_KEY",
    "VOLCENGINE_SECRET_KEY",
    "VOLCENGINE_SESSION_TOKEN",
    "AGENTKIT_TOOL_REGION",
    "AGENTKIT_TOOL_SERVICE_CODE",
    "AGENTKIT_TOOL_HOST",
    "AGENTKIT_TOOL_SCHEME",
    "AGENTKIT_SKILL_HOST",
    "AGENTKIT_TOP_SCHEME",
    "SKILL_SPACE_ID",
)


def hide_adk_discovery_route(fastapi_app) -> int:
    """Hide ADK discovery so the public Runtime console uses ``/invoke``.

    ``AgentkitAgentServerApp`` exposes the complete ADK development API.  The
    AgentKit console probes ``GET /list-apps`` and, when it succeeds, switches
    from the public Runtime contract to the ADK debug flow
    (session lookup/create followed by ``/run_sse``).  OAuth JWT Runtime
    gateways are intended to call the public ``POST /invoke`` route instead.

    The compatibility ``/invoke`` handler already creates the ADK session
    internally, so hiding discovery does not disable session persistence or
    any Agent capability.  The local UI also calls ``/invoke`` directly.
    """
    routes = fastapi_app.router.routes
    retained_routes = []
    removed = 0
    for route in routes:
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "path", None) == "/list-apps" and "GET" in methods:
            removed += 1
            continue
        retained_routes.append(route)
    routes[:] = retained_routes
    return removed


class PublicInvokeOriginMiddleware:
    """Keep ADK's browser-origin guard away from the public Runtime API.

    ADK's origin check protects its browser development endpoints.  AgentKit's
    public ``POST /invoke`` endpoint is instead authenticated by the Runtime
    gateway's bearer credential.  Removing ``Origin`` only on that one route
    prevents ADK from mistaking a console or local-UI call for an unsafe ADK UI
    request.  Every other route reaches ADK's origin guard unchanged.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope.get("type") == "http"
            and scope.get("method") == "POST"
            and scope.get("path") == "/invoke"
        ):
            scope = dict(scope)
            scope["headers"] = [
                (name, value)
                for name, value in scope.get("headers", [])
                if name.lower() != b"origin"
            ]
        await self.app(scope, receive, send)


def platform_postgres_configured() -> bool:
    """Whether AgentKit injected a complete managed PostgreSQL connection.

    The AgentKit session-management component injects the five
    ``DATABASE_POSTGRESQL_*`` variables.  VeADK's PostgreSQL backend consumes
    those variables itself, including password escaping and the compatible
    SQLAlchemy driver choice, so this application must not log or construct a
    credential-bearing URL.
    """
    return all(os.getenv(key) for key in _POSTGRES_ENV_KEYS)


def long_term_memory_enabled() -> bool:
    """Allow an isolated short-term-session verification without MEM0 reads."""
    return os.getenv("ENABLE_LONG_TERM_MEMORY", "true").lower() not in {
        "0",
        "false",
        "no",
    }


def platform_aio_sandbox_configured() -> bool:
    """Whether an AgentKit Tool ID is available for an explicit AIO request."""
    return bool(os.getenv("AGENTKIT_TOOL_ID"))


def platform_skills_sandbox_configured() -> bool:
    """Whether an AgentKit Tool ID is available for an explicit Skills request."""
    return bool(os.getenv("AGENTKIT_TOOL_ID"))


def platform_sandbox_configured() -> bool:
    """Whether the Runtime has one platform-injected Tool ID."""
    return bool(os.getenv("AGENTKIT_TOOL_ID"))


def configured_skill_space_ids() -> list[str]:
    """Return the AgentKit Skills Space IDs configured for this Runtime.

    ``SKILL_SPACE_ID`` is configured on the Runtime for the Skills Center. VeADK
    accepts a comma-separated string here and resolves each ``ss-...`` space
    through AgentKit's ``ListSkillsBySpaceId`` API during Agent construction.
    It is intentionally separate from ``AGENTKIT_TOOL_ID``: the former tells
    the Agent which Skill metadata to load, while the latter selects the
    currently associated Sandbox execution tool.
    """
    return [item.strip() for item in os.getenv("SKILL_SPACE_ID", "").split(",") if item.strip()]


def configure_hybrid_skills_endpoint() -> None:
    """Map AgentKit's injected hybrid-cloud control-plane endpoint for Skills.

    VeADK uses ``AGENTKIT_SKILL_HOST`` and ``AGENTKIT_TOP_SCHEME`` when it
    discovers the metadata in ``SKILL_SPACE_ID``.  In an AgentKit Runtime the
    same endpoint is injected under ``VOLCENGINE_AGENTKIT_HOST`` and
    ``VOLCENGINE_AGENTKIT_SCHEME``.  Map only when an operator has not set an
    explicit Skills endpoint, so a public-cloud or custom endpoint keeps its
    configured precedence.
    """
    mappings = (
        ("AGENTKIT_SKILL_HOST", "VOLCENGINE_AGENTKIT_HOST"),
        ("AGENTKIT_TOP_SCHEME", "VOLCENGINE_AGENTKIT_SCHEME"),
    )
    for target, source in mappings:
        if not os.getenv(target) and os.getenv(source):
            os.environ[target] = os.environ[source]
            logger.info("Skills control-plane endpoint configured from %s", source)


def hybrid_skills_sandbox_env(tool_state: dict | None = None) -> dict[str, str]:
    """Return the minimal Hybrid Cloud context needed inside Skills Sandbox.

    The Runtime and the Sandbox are separate processes.  ``veadk-python``
    uses ``CLOUD_PROVIDER=vestack`` plus the AgentKit TOP endpoint and request
    credentials to request a MinIO temporary download URL for a published
    Skill.  Those values may arrive either as Runtime environment variables or
    as request-scoped ``tool_context.state`` credentials.

    Values are deliberately returned, not logged.  ``run_sandbox_agent``
    injects them into the isolated child process only for the current call.
    """
    configure_hybrid_skills_endpoint()
    state = tool_state or {}
    forwarded: dict[str, str] = {}
    for key in _SKILLS_SANDBOX_CONTEXT_ENV_KEYS:
        value = os.getenv(key) or state.get(key)
        if value:
            forwarded[key] = str(value)
    return forwarded


def build_short_term_memory(memory_factory):
    """Select explicit local URL, platform PostgreSQL, or local fallback."""
    # Retain this escape hatch for local development.  In the managed Runtime,
    # prefer the component-injected DATABASE_POSTGRESQL_* variables below.
    session_database_url = os.getenv("SESSION_DATABASE_URL", "")
    if session_database_url:
        logger.info("Short-term session backend: explicit PostgreSQL URL (local override).")
        return memory_factory(backend="postgresql", db_url=session_database_url)
    if platform_postgres_configured():
        # PostgreSqlSTMBackend reads DATABASE_POSTGRESQL_* directly.
        logger.info("Short-term session backend: AgentKit managed PostgreSQL.")
        return memory_factory(backend="postgresql")
    missing = [key for key in _POSTGRES_ENV_KEYS if not os.getenv(key)]
    logger.warning(
        "Short-term session backend: local fallback; missing AgentKit PostgreSQL env keys=%s",
        ",".join(missing),
    )
    return memory_factory(backend="local")


def customer_service_demo(
    message: str,
    tenant_id: str = "demo-bank",
    user_id: str = "user-001",
    session_id: str = "session-001",
) -> str:
    """Run a confirmed service workflow or demo-only fallback.

    For policy, product rules, document citations, and other factual questions,
    call ``load_knowledgebase`` first. Do not use this tool as a source of
    knowledge-base content in a live Runtime.
    """
    return json.dumps(
        service.chat(
            message,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
        ).to_dict(),
        ensure_ascii=False,
    )


def build_agent():
    """Build the VeADK agent lazily so tests do not require cloud packages."""
    # Some ModelCenter routes return duplicate `Server` response headers.
    # LiteLLM's default aiohttp transport rejects those responses at HTTP
    # parsing time, while its HTTPX transport accepts them.  Prefer HTTPX for
    # this hybrid-cloud sample; set LITELLM_DISABLE_AIOHTTP_TRANSPORT=false to
    # restore LiteLLM's default transport in an environment that does not need
    # the compatibility mode.
    if os.getenv("LITELLM_DISABLE_AIOHTTP_TRANSPORT", "true").lower() in {
        "1",
        "true",
        "yes",
    }:
        import litellm

        litellm.disable_aiohttp_transport = True

    configure_hybrid_skills_endpoint()

    from google.adk.agents.context import Context
    from veadk import Agent

    app_name = "hybrid_cloud_customer_service"
    knowledge = build_platform_knowledge(app_name)
    # This switch is useful for platform acceptance: it lets an operator prove
    # that PostgreSQL session persistence works without a matching MEM0 result
    # influencing the model answer.  Production defaults to enabled.
    long_term_memory = build_platform_memory(app_name) if long_term_memory_enabled() else None

    optional_features = {}
    if os.getenv("DIRECT_CONTAINER_MODE", "false").lower() in {"1", "true", "yes"}:
        # Keep the managed/public Runtime path unchanged. Direct-container
        # exporter construction lives behind this narrow opt-in seam.
        from direct_observability import build_direct_container_tracers

        direct_tracers = build_direct_container_tracers(app_name)
        if direct_tracers:
            optional_features["tracers"] = direct_tracers
    if knowledge is not None:
        optional_features["knowledgebase"] = knowledge
    if long_term_memory is not None:
        optional_features["long_term_memory"] = long_term_memory
        # VeADK's built-in callback fetches the persisted session after an
        # invocation and force-saves the previous session on a session switch.
        # That avoids racing this application's callback against session
        # persistence during cross-session verification.
        optional_features["auto_save_session"] = True
        logger.info("AgentKit MEM0 long-term memory is enabled with session-switch saving.")
    else:
        logger.warning(
            "AgentKit MEM0 long-term memory is disabled: no injected MEM0 binding was found."
        )

    skill_space_ids = configured_skill_space_ids()
    if skill_space_ids:
        # This is the Skills Center integration point.  VeADK treats every
        # value as an AgentKit Skills Space ID (for example ``ss-xxx``), lists
        # its Skill metadata, and adds the available Skill names/descriptions
        # to the Agent instruction.  Actual execution remains explicit via
        # ``execute_skills`` and the single platform Tool ID below.
        optional_features["skills"] = skill_space_ids
        optional_features["skills_mode"] = "skills_sandbox"
        optional_features["enable_dynamic_load_skills"] = True
        logger.info("AgentKit Skills Center spaces enabled: count=%s", len(skill_space_ids))

    tools = [customer_service_demo]
    mcp_router = build_platform_mcp_router()
    if mcp_router is not None:
        # AgentKit injects the associated MCP toolset router URL and key.
        # VeADK performs tool discovery, semantic routing and the final MCP
        # call; business code never connects to an individual MCP service.
        tools.append(mcp_router)
    else:
        logger.info("AgentKit MCP disabled: no associated toolset configuration injected.")
    if a2a_data_agent_configured():
        # The remote data agent has its own Runtime, Agent Card and API key.
        # This tool first discovers its advertised capabilities, then sends a
        # standard A2A ``message/send`` request.  Do not register it before
        # the operator has supplied the remote endpoint.
        tools.append(delegate_complaint_trend_analysis)
        logger.info("A2A complaint data-agent delegation enabled.")
    else:
        logger.info("A2A complaint data-agent delegation disabled: no endpoint configured.")
    if platform_sandbox_configured():
        # The Runtime has one associated Tool ID.  Both client functions are
        # exposed so an operator can explicitly request run_code (AIO) or
        # execute_skills (Skills).  The prompt forbids guessing the type.
        from veadk.tools.builtin_tools._agentkit import resolve_agentkit_tool_id
        from veadk.tools.builtin_tools.run_code import run_code
        from veadk.tools.builtin_tools.run_sandbox_agent import run_sandbox_agent

        def execute_skills(
            workflow_prompt: str,
            tool_context=None,
        ) -> str:
            """Execute a published Skills Center workflow in the Skills Sandbox.

            This wrapper retains VeADK's official single ``AGENTKIT_TOOL_ID``
            execution model.  It additionally forwards the Hybrid Cloud
            context that the nested Sandbox needs to use the MinIO signed-URL
            download implementation introduced for ``CLOUD_PROVIDER=vestack``.
            """
            tool_state = tool_context.state if tool_context is not None else None
            return run_sandbox_agent(
                workflow_prompt=workflow_prompt,
                tool_id=resolve_agentkit_tool_id("AGENTKIT_TOOL_ID_SKILLS"),
                tool_context=tool_context,
                timeout=900,
                extra_env_vars=hybrid_skills_sandbox_env(tool_state),
            )

        # ``from __future__ import annotations`` stores annotations as strings.
        # ADK later resolves tool annotations against module globals, whereas
        # ``Context`` is intentionally imported lazily inside ``build_agent``.
        # Bind the real class after defining the closure so ADK can inject the
        # context and omit it from the model-visible JSON schema.
        execute_skills.__annotations__["tool_context"] = Context

        tools.append(run_code)
        tools.append(execute_skills)
        logger.info(
            "AgentKit run_code and execute_skills functions enabled for explicit tool selection."
        )
    else:
        logger.info("AgentKit Sandbox functions disabled: no AgentKit tool ID injected.")

    agent = Agent(
        name="hybrid_cloud_customer_service",
        description="Hybrid-cloud enterprise customer-service demo.",
        instruction=INSTRUCTION,
        # VeADK 1.1.x validates these fields as strings. Live deployment still
        # requires real model values; empty strings only keep deterministic
        # local imports and tests from passing None into Agent validation.
        model_name=settings.model_name or "",
        model_api_key=settings.model_api_key or "",
        model_api_base=settings.model_api_base or "",
        # Keep the deterministic business workflow available for local demo
        # tests.  In live mode, the tool description below makes policy
        # questions use VeADK's injected ``load_knowledgebase`` tool instead.
        tools=tools,
        **optional_features,
    )
    normalize_knowledge_tool_metadata(agent.tools)
    normalize_memory_tool_metadata(agent.tools)
    return agent


def main() -> None:
    bind_host = os.getenv("APP_BIND_HOST", "0.0.0.0")
    if settings.effective_mode == "demo":
        import uvicorn

        uvicorn.run("demo_app:app", host=bind_host, port=int(os.getenv("PORT", "8000")))
        return

    from agentkit.apps import AgentkitAgentServerApp
    from veadk.memory import ShortTermMemory

    short_term_memory = build_short_term_memory(ShortTermMemory)
    app = AgentkitAgentServerApp(agent=build_agent(), short_term_memory=short_term_memory)
    if os.getenv("DIRECT_CONTAINER_MODE", "false").lower() in {"1", "true", "yes"}:
        # Uvicorn applies logging configuration after Agent construction.
        # Reattach the handler during startup for access/error log export.
        from direct_observability import ensure_direct_otel_logging_handlers

        app.app.add_event_handler("startup", ensure_direct_otel_logging_handlers)
    removed_discovery_routes = hide_adk_discovery_route(app.app)
    logger.info(
        "ADK online-test discovery disabled; public /invoke remains enabled: routes=%s",
        removed_discovery_routes,
    )
    # The Knowledge API key is supplied by the caller in Authorization.  This
    # middleware keeps it request-scoped for platform_knowledge.py; it never
    # logs or persists the credential.
    app.app.add_middleware(RequestAuthorizationMiddleware)
    # The gateway authenticates /invoke with its bearer credential.  Bypass
    # only ADK's browser-development Origin check for that public API route.
    app.app.add_middleware(PublicInvokeOriginMiddleware)
    app.run(host=bind_host, port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
