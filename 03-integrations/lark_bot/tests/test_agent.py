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


class FakeRunner:
    instances = []

    def __init__(self, agent, app_name):
        self.agent = agent
        self.app_name = app_name
        self.calls = []
        self.__class__.instances.append(self)

    async def run(self, prompt, user_id, session_id):
        self.calls.append((prompt, user_id, session_id))
        return "runner-result"


class FakeShortTermMemory:
    def __init__(self, backend):
        self.backend = backend


def load_agent_module():
    veadk = types.ModuleType("veadk")
    veadk.Agent = FakeAgent
    veadk.Runner = FakeRunner

    memory = types.ModuleType("veadk.memory")
    memory.ShortTermMemory = FakeShortTermMemory

    web_search_module = types.ModuleType("veadk.tools.builtin_tools.web_search")
    web_search_module.web_search = object()

    sys.modules["veadk"] = veadk
    sys.modules["veadk.memory"] = memory
    sys.modules["veadk.tools"] = types.ModuleType("veadk.tools")
    sys.modules["veadk.tools.builtin_tools"] = types.ModuleType(
        "veadk.tools.builtin_tools"
    )
    sys.modules["veadk.tools.builtin_tools.web_search"] = web_search_module

    spec = importlib.util.spec_from_file_location("lark_bot_agent_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_agent_is_configured_with_lark_app_name():
    FakeRunner.instances.clear()
    module = load_agent_module()

    assert module.APP_NAME == "LARK_AGENT"
    assert module.runner.app_name == "LARK_AGENT"
    assert module.root_agent.kwargs["name"] == "chatbot"
    assert module.root_agent.kwargs["short_term_memory"].backend == "local"
    assert len(module.root_agent.kwargs["tools"]) == 1


def test_run_agent_delegates_to_runner():
    FakeRunner.instances.clear()
    module = load_agent_module()

    result = asyncio.run(module.run_agent("hello", "user-1", "session-1"))

    assert result == "runner-result"
    assert module.runner.calls == [("hello", "user-1", "session-1")]
