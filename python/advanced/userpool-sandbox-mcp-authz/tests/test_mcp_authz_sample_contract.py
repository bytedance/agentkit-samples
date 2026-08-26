import importlib
import json
import os
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

AGENT_NAME = "userpool_sandbox_mcp_authz"
SANDBOX_PROMPT_ENV = "SKILL_SANDBOX_MCP_PROMPT"


def install_dependency_stubs():
    class FakeAgent:
        def __init__(self, *, name, description, instruction, tools, **kwargs):
            self.name = name
            self.description = description
            self.instruction = instruction
            self.tools = tools
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeAgentkitAgentServerApp:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.app = FakeFastAPIApp(server_kwargs=kwargs)
            self.app.router.routes.append(
                SimpleNamespace(path="/", methods={"POST"}, name="sdk_root_route")
            )

        def run(self, **kwargs):
            self.run_kwargs = kwargs

    class FakeFastAPIApp:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.get_routes = []
            self.middlewares = []
            self.mounts = []
            self.router = SimpleNamespace(routes=[])

        def get(self, path):
            def decorator(func):
                self.get_routes.append((path, func))
                self.router.routes.append(
                    SimpleNamespace(path=path, methods={"GET"}, name=func.__name__)
                )
                return func

            return decorator

        def add_middleware(self, middleware):
            self.middlewares.append(middleware)

        def mount(self, path, app, name=None):
            self.mounts.append((path, app, name))

    class FakeStaticFiles:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeHTMLResponse:
        def __init__(self, content):
            self.content = content

    google = sys.modules.setdefault("google", types.ModuleType("google"))
    google_adk = types.ModuleType("google.adk")
    google_adk_apps = types.ModuleType("google.adk.apps")
    google_adk_apps_app = types.ModuleType("google.adk.apps.app")
    google_adk_cli = types.ModuleType("google.adk.cli")
    google_adk_cli_fast_api = types.ModuleType("google.adk.cli.fast_api")
    google_adk_tools = types.ModuleType("google.adk.tools")
    google_adk_tools.ToolContext = object

    veadk = types.ModuleType("veadk")
    veadk.Agent = FakeAgent
    veadk.__file__ = str(
        PROJECT_ROOT / ".venv/lib/python3.12/site-packages/veadk/__init__.py"
    )
    veadk_auth = types.ModuleType("veadk.auth")
    veadk_auth_middleware = types.ModuleType("veadk.auth.middleware")
    veadk_oauth2_auth = types.ModuleType("veadk.auth.middleware.oauth2_auth")
    veadk_tools = types.ModuleType("veadk.tools")
    veadk_utils = types.ModuleType("veadk.utils")
    veadk_utils_auth = types.ModuleType("veadk.utils.auth")
    veadk_builtin_tools = types.ModuleType("veadk.tools.builtin_tools")
    veadk_execute_skills = types.ModuleType("veadk.tools.builtin_tools.execute_skills")
    agentkit = types.ModuleType("agentkit")
    agentkit_apps = types.ModuleType("agentkit.apps")
    fastapi_staticfiles = types.ModuleType("fastapi.staticfiles")
    starlette = types.ModuleType("starlette")
    starlette_responses = types.ModuleType("starlette.responses")
    starlette_types = types.ModuleType("starlette.types")
    uvicorn = types.ModuleType("uvicorn")

    def fake_execute_skills(**kwargs):
        return {"called": kwargs}

    def fake_build_auth_config(**kwargs):
        return SimpleNamespace(
            exchanged_auth_credential=SimpleNamespace(
                credential_key=kwargs.get("credential_key"),
                token=kwargs.get("token"),
                auth_method=kwargs.get("auth_method"),
            )
        )

    class FakeOAuth2Config:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.cookie_secure = None
            self.api_path_prefixes = None
            self.logout_redirect_url = None
            self.end_session_url = None

        @classmethod
        def from_veidentity(cls, **kwargs):
            return cls(**kwargs)

    def fake_fetch_oidc_discovery(issuer):
        return SimpleNamespace(
            authorization_endpoint=f"{issuer}/authorize",
            token_endpoint=f"{issuer}/token",
            userinfo_endpoint=f"{issuer}/userinfo",
            issuer=issuer,
            jwks_uri=f"{issuer}/jwks",
        )

    def fake_get_fast_api_app(**kwargs):
        return FakeFastAPIApp(**kwargs)

    class FakeAdkApp:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]
            self.root_agent = kwargs["root_agent"]
            self.kwargs = kwargs

    def fake_setup_oauth2(app, config, **kwargs):
        app.oauth2_config = config
        app.oauth2_kwargs = kwargs

    def fake_uvicorn_run(*args, **kwargs):
        return None

    agentkit_apps.AgentkitAgentServerApp = FakeAgentkitAgentServerApp
    google_adk_apps_app.App = FakeAdkApp
    google_adk_cli_fast_api.get_fast_api_app = fake_get_fast_api_app
    veadk_execute_skills.execute_skills = fake_execute_skills
    veadk_utils_auth.build_auth_config = fake_build_auth_config
    veadk_oauth2_auth.OAuth2Config = FakeOAuth2Config
    veadk_oauth2_auth._fetch_oidc_discovery = fake_fetch_oidc_discovery
    veadk_oauth2_auth.setup_oauth2 = fake_setup_oauth2
    fastapi_staticfiles.StaticFiles = FakeStaticFiles
    starlette_responses.HTMLResponse = FakeHTMLResponse
    uvicorn.run = fake_uvicorn_run
    starlette_types.ASGIApp = object
    starlette_types.Message = dict
    starlette_types.Receive = object
    starlette_types.Scope = dict
    starlette_types.Send = object

    sys.modules.update(
        {
            "google": google,
            "google.adk": google_adk,
            "google.adk.apps": google_adk_apps,
            "google.adk.apps.app": google_adk_apps_app,
            "google.adk.cli": google_adk_cli,
            "google.adk.cli.fast_api": google_adk_cli_fast_api,
            "google.adk.tools": google_adk_tools,
            "agentkit": agentkit,
            "agentkit.apps": agentkit_apps,
            "veadk": veadk,
            "veadk.auth": veadk_auth,
            "veadk.auth.middleware": veadk_auth_middleware,
            "veadk.auth.middleware.oauth2_auth": veadk_oauth2_auth,
            "veadk.utils": veadk_utils,
            "veadk.utils.auth": veadk_utils_auth,
            "veadk.tools": veadk_tools,
            "veadk.tools.builtin_tools": veadk_builtin_tools,
            "veadk.tools.builtin_tools.execute_skills": veadk_execute_skills,
            "fastapi.staticfiles": fastapi_staticfiles,
            "starlette": starlette,
            "starlette.responses": starlette_responses,
            "starlette.types": starlette_types,
            "uvicorn": uvicorn,
        }
    )


def import_agent_module():
    install_dependency_stubs()
    sys.modules.pop("assistant", None)
    sys.modules.pop("assistant.agent", None)
    return importlib.import_module("assistant.agent")


def import_main_module():
    install_dependency_stubs()
    sys.modules.pop("assistant", None)
    sys.modules.pop("assistant.agent", None)
    sys.modules.pop("main", None)
    return importlib.import_module("main")


def import_local_ui_module():
    install_dependency_stubs()
    for module_name in ("assistant", "assistant.agent", "app"):
        sys.modules.pop(module_name, None)
    with mock.patch.dict(
        os.environ,
        {
            "OAUTH2_ISSUER_URI": "https://issuer.example.com",
            "OAUTH2_CLIENT_ID": "client-id",
            "HOST": "127.0.0.1",
        },
        clear=False,
    ):
        return importlib.import_module("app")


class SkillsSandboxExperimentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent_module = import_agent_module()

    def test_root_agent_is_skills_sandbox_mcp_experiment(self):
        tool_names = [tool.__name__ for tool in self.agent_module.root_agent.tools]

        self.assertEqual(self.agent_module.root_agent.name, AGENT_NAME)
        self.assertEqual(tool_names, ["call_mcp_tool_via_skills_sandbox"])
        self.assertIn(
            "Skills Sandbox MCP experiment",
            self.agent_module.root_agent.instruction,
        )
        self.assertIn(
            "Skills Sandbox already owns the MCP tool configuration",
            self.agent_module.root_agent.instruction,
        )
        self.assertIn(
            "Do not reveal access tokens", self.agent_module.root_agent.instruction
        )
        self.assertNotIn("gateway rejects", self.agent_module.root_agent.instruction)
        self.assertNotIn("401 or 403", self.agent_module.root_agent.instruction)
        self.assertNotIn(
            "inbound_auth_received", self.agent_module.root_agent.instruction
        )

    def test_call_mcp_tool_delegates_user_request_to_execute_skills(self):
        tool_context = SimpleNamespace(name="tool-context")

        with mock.patch.object(
            self.agent_module,
            "execute_skills",
            return_value={"content": "sandbox result"},
        ) as execute:
            result = self.agent_module.call_mcp_tool_via_skills_sandbox(
                "Use the MCP tool to inspect the sandbox resource.",
                tool_context,
            )

        execute.assert_called_once()
        kwargs = execute.call_args.kwargs
        self.assertIn("inspect the sandbox resource", kwargs["workflow_prompt"])
        self.assertIn("Do not reveal access tokens", kwargs["workflow_prompt"])
        self.assertIs(kwargs["tool_context"], tool_context)
        self.assertEqual(kwargs["timeout"], 1800)
        self.assertTrue(result["ok"])
        self.assertEqual(result["stage"], "execute_skills_mcp_experiment")
        self.assertEqual(result["credential_key"], "inbound_auth")
        self.assertFalse(result["skill_sandbox"]["runtime_mcp_env_required"])
        self.assertEqual(result["inbound_auth_source"], "local_webui_state_delta")
        self.assertFalse(result["local_inbound_auth_stored"])

    def test_call_mcp_tool_stores_local_webui_token_to_credential_service(self):
        class FakeCredentialService:
            def __init__(self):
                self.calls = []

            async def set_credential(self, **kwargs):
                self.calls.append(kwargs)

        credential_service = FakeCredentialService()
        tool_context = SimpleNamespace(
            state={
                self.agent_module.LOCAL_INBOUND_AUTH_TOKEN_STATE_KEY: "access-token"
            },
            _invocation_context=SimpleNamespace(
                app_name="assistant",
                user_id="user-1",
                credential_service=credential_service,
            ),
        )

        with mock.patch.object(
            self.agent_module,
            "execute_skills",
            return_value={"content": "sandbox result"},
        ) as execute:
            result = self.agent_module.call_mcp_tool_via_skills_sandbox(
                "Call the configured MCP tool.",
                tool_context,
            )

        execute.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertTrue(result["local_inbound_auth_stored"])
        self.assertEqual(len(credential_service.calls), 1)
        self.assertEqual(credential_service.calls[0]["credential_key"], "inbound_auth")
        self.assertEqual(
            credential_service.calls[0]["credential"].token, "access-token"
        )

    def test_call_mcp_tool_supports_prompt_template_override(self):
        tool_context = SimpleNamespace(name="tool-context")
        template = "Use production policy. Request: {user_request}"

        with mock.patch.dict(os.environ, {SANDBOX_PROMPT_ENV: template}, clear=False):
            with mock.patch.object(
                self.agent_module,
                "execute_skills",
                return_value="ok",
            ) as execute:
                result = self.agent_module.call_mcp_tool_via_skills_sandbox(
                    "List invoices.",
                    tool_context,
                )

        self.assertEqual(
            execute.call_args.kwargs["workflow_prompt"],
            "Use production policy. Request: List invoices.",
        )
        self.assertEqual(result["prompt_source"], "env")

    def test_call_mcp_tool_reports_execute_skills_error_without_token_language(self):
        tool_context = SimpleNamespace(name="tool-context")

        with mock.patch.object(
            self.agent_module,
            "execute_skills",
            side_effect=RuntimeError("sandbox unavailable"),
        ):
            result = self.agent_module.call_mcp_tool_via_skills_sandbox(
                "Call the MCP search tool.",
                tool_context,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "execute_skills_mcp_experiment")
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertIn("sandbox unavailable", result["error"]["message"])
        self.assertNotIn("inbound_auth_received", json.dumps(result))

    def test_main_keeps_optional_cloud_agent_server_entrypoint(self):
        main_module = import_main_module()

        self.assertIs(main_module.server.kwargs["agent"], main_module.root_agent)
        self.assertTrue(main_module.server.kwargs["enable_auth"])
        self.assertIs(main_module.app, main_module.server.app)

    def test_local_webui_app_uses_veadk_webui_and_token_state_bridge(self):
        app_module = import_local_ui_module()

        self.assertEqual(app_module.AGENTS_DIR, str(PROJECT_ROOT))
        self.assertEqual(app_module.app.kwargs["agents_dir"], str(PROJECT_ROOT))
        self.assertFalse(app_module.app.kwargs["web"])
        self.assertTrue(app_module.app.kwargs["auto_create_session"])
        self.assertIn(
            app_module.UserTokenStateASGIMiddleware, app_module.app.middlewares
        )
        self.assertIn(("/", mock.ANY, "webui"), app_module.app.mounts)
        self.assertIn(
            "/ping",
            [path for path, _ in app_module.app.get_routes],
        )
        self.assertIn(
            "/web/auth-config",
            [path for path, _ in app_module.app.get_routes],
        )
        self.assertEqual(
            app_module.app.oauth2_kwargs["exempt_paths"],
            {"/", "/index.html", "/favicon.ico", "/ping", "/web/auth-config"},
        )

    def test_project_assets_match_experiment_shape(self):
        env_text = (PROJECT_ROOT / ".env.example").read_text()
        agentkit_text = (PROJECT_ROOT / "agentkit.yaml").read_text()
        readme = (PROJECT_ROOT / "README.md").read_text()
        requirements = (PROJECT_ROOT / "requirements.txt").read_text()

        self.assertIn("agent_name: userpool-sandbox-mcp-authz", agentkit_text)
        self.assertIn("agent_type: WebServer App", agentkit_text)
        self.assertIn("SKILL_SANDBOX_MCP_PROMPT", agentkit_text)
        self.assertIn("AGENTKIT_TOOL_ID:", agentkit_text)
        self.assertIn("CLOUD_CLIENT_REDIRECT_URI", env_text)
        self.assertIn("OAUTH2_TESTAPP_REDIRECT_URI", env_text)
        self.assertIn("AGENT_RUNTIME_URL", env_text)
        self.assertIn("Flask", requirements)
        self.assertIn("veadk-python==1.1.5", requirements)
        self.assertIn("# User Pool + Skills Sandbox MCP experiment", readme)
        self.assertIn("uv run python app.py", readme)
        self.assertIn("uv run python oauth2_testapp.py", readme)
        self.assertIn("uv run python cloud_client_app.py", readme)
        self.assertIn("uv run python exchange_user_token_for_tip.py", readme)
        self.assertFalse((PROJECT_ROOT / "assistant/mcp_authz.py").exists())

    def test_token_and_cloud_client_helpers_are_present(self):
        token_helper = (PROJECT_ROOT / "oauth2_testapp.py").read_text()
        tip_helper = (PROJECT_ROOT / "exchange_user_token_for_tip.py").read_text()
        cloud_client = (PROJECT_ROOT / "cloud_client_app.py").read_text()

        self.assertIn("Access Token", token_helper)
        self.assertIn("OAUTH2_TESTAPP_REDIRECT_URI", token_helper)
        self.assertIn("get_workload_access_token", tip_helper)
        self.assertIn("X-Ve-TIP-Token", tip_helper)
        self.assertIn("AGENT_RUNTIME_URL", cloud_client)
        self.assertIn("run_sse", cloud_client)
        self.assertIn("/api/run-cloud", cloud_client)
        self.assertIn("invoke", cloud_client)
        self.assertIn("Authorization", cloud_client)
        self.assertIn("setup_oauth2", cloud_client)
        self.assertIn("OAuth2RoutePaths", cloud_client)
        self.assertIn("_oauth2_route_paths", cloud_client)
        self.assertIn("/oauth2/callback", cloud_client)
        self.assertIn("HTMLResponse", cloud_client)
        self.assertIn("/api/me", cloud_client)
        self.assertIn("/api/config", cloud_client)
        self.assertIn("CLOUD_AGENT_CALL_PATH", cloud_client)
        self.assertIn("_ensure_adk_session", cloud_client)
        self.assertIn('"prompt": prompt', cloud_client)
        self.assertIn('"new_message"', cloud_client)
        self.assertIn("apps/{APP_NAME}/users/{user_id}/sessions", cloud_client)
        self.assertIn("_stream_invoke", cloud_client)
        self.assertIn("_stream_run_sse", cloud_client)
        self.assertIn("_cloud_event_stream", cloud_client)
        self.assertNotIn("web_runtime_proxy", cloud_client)
        self.assertNotIn("runtime-route-channel", cloud_client)
        self.assertNotIn("local_inbound_auth_ref", cloud_client)


if __name__ == "__main__":
    unittest.main()
