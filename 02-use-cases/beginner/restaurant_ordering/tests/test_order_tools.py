from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "agent.py"


class FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.name = kwargs.get("name")


class FakeApp:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeAgentkitAgentServerApp:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, host, port):
        self.host = host
        self.port = port


class FakeBasePlugin:
    def __init__(self, name=None):
        self.name = name


class FakeShortTermMemory:
    def __init__(self, backend):
        self.backend = backend


def install_stubs(monkeypatch):
    agentkit_apps = types.ModuleType("agentkit.apps")
    agentkit_apps.AgentkitAgentServerApp = FakeAgentkitAgentServerApp

    google_adk_agents_base = types.ModuleType("google.adk.agents.base_agent")
    google_adk_agents_base.BaseAgent = object
    google_adk_callback = types.ModuleType("google.adk.agents.callback_context")
    google_adk_callback.CallbackContext = object
    google_adk_apps = types.ModuleType("google.adk.apps")
    google_adk_apps.App = FakeApp
    google_adk_app_module = types.ModuleType("google.adk.apps.app")
    google_adk_app_module.EventsCompactionConfig = lambda **kwargs: dict(kwargs)
    google_adk_llm_request = types.ModuleType("google.adk.models.llm_request")
    google_adk_llm_request.LlmRequest = object
    google_adk_plugins_base = types.ModuleType("google.adk.plugins.base_plugin")
    google_adk_plugins_base.BasePlugin = FakeBasePlugin
    google_adk_context_filter = types.ModuleType(
        "google.adk.plugins.context_filter_plugin"
    )
    google_adk_context_filter.ContextFilterPlugin = lambda **kwargs: dict(kwargs)
    google_adk_save_files = types.ModuleType(
        "google.adk.plugins.save_files_as_artifacts_plugin"
    )
    google_adk_save_files.SaveFilesAsArtifactsPlugin = lambda: "save-files-plugin"
    google_adk_tool_context = types.ModuleType("google.adk.tools.tool_context")
    google_adk_tool_context.ToolContext = object

    google_genai = types.ModuleType("google.genai")
    google_genai_types = types.SimpleNamespace(
        GenerateContentConfig=lambda **kwargs: dict(kwargs),
        SafetySetting=lambda **kwargs: dict(kwargs),
        HarmCategory=types.SimpleNamespace(HARM_CATEGORY_DANGEROUS_CONTENT="danger"),
    )
    google_genai.types = google_genai_types

    veadk_agent = types.ModuleType("veadk.agent")
    veadk_agent.Agent = FakeAgent
    veadk_memory = types.ModuleType("veadk.memory.short_term_memory")
    veadk_memory.ShortTermMemory = FakeShortTermMemory
    veadk_web_search = types.ModuleType("veadk.tools.builtin_tools.web_search")
    veadk_web_search.web_search = lambda query: query

    modules = {
        "agentkit.apps": agentkit_apps,
        "google.adk.agents.base_agent": google_adk_agents_base,
        "google.adk.agents.callback_context": google_adk_callback,
        "google.adk.apps": google_adk_apps,
        "google.adk.apps.app": google_adk_app_module,
        "google.adk.models.llm_request": google_adk_llm_request,
        "google.adk.plugins.base_plugin": google_adk_plugins_base,
        "google.adk.plugins.context_filter_plugin": google_adk_context_filter,
        "google.adk.plugins.save_files_as_artifacts_plugin": google_adk_save_files,
        "google.adk.tools.tool_context": google_adk_tool_context,
        "google.genai": google_genai,
        "veadk.agent": veadk_agent,
        "veadk.memory.short_term_memory": veadk_memory,
        "veadk.tools.builtin_tools.web_search": veadk_web_search,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def load_module(monkeypatch):
    install_stubs(monkeypatch)
    spec = importlib.util.spec_from_file_location("restaurant_order_agent", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_add_to_order_initializes_and_appends_state(monkeypatch):
    module = load_module(monkeypatch)
    context = types.SimpleNamespace(state={})

    result = asyncio.run(module.add_to_order("Mapo Tofu", context))

    assert result == "I've added Mapo Tofu to your order."
    assert context.state["order"] == ["Mapo Tofu"]


def test_add_to_order_preserves_existing_items(monkeypatch):
    module = load_module(monkeypatch)
    context = types.SimpleNamespace(state={"order": ["Dumplings"]})

    asyncio.run(module.add_to_order("Wonton Soup", context))

    assert context.state["order"] == ["Dumplings", "Wonton Soup"]


def test_summarize_order_reports_empty_order(monkeypatch):
    module = load_module(monkeypatch)
    context = types.SimpleNamespace(state={})

    assert asyncio.run(module.summarize_order(context)) == "You haven't ordered anything yet."


def test_summarize_order_formats_order_lines(monkeypatch):
    module = load_module(monkeypatch)
    context = types.SimpleNamespace(state={"order": ["Dumplings", "Fried Rice"]})

    result = asyncio.run(module.summarize_order(context))

    assert result == "Here is your order so far:\n- Dumplings\n- Fried Rice"


def test_count_invocation_plugin_counts_callbacks(monkeypatch):
    module = load_module(monkeypatch)
    plugin = module.CountInvocationPlugin()

    asyncio.run(plugin.before_agent_callback(agent=object(), callback_context=object()))
    asyncio.run(
        plugin.before_model_callback(
            callback_context=object(),
            llm_request=object(),
        )
    )

    assert plugin.agent_count == 1
    assert plugin.llm_request_count == 1
    assert plugin.tool_count == 0
