from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"


class FakeResponse:
    def __init__(self, ok=True, code=0, msg="ok", log_id="log-1"):
        self._ok = ok
        self.code = code
        self.msg = msg
        self._log_id = log_id

    def success(self):
        return self._ok

    def get_log_id(self):
        return self._log_id


class RecordingMessageApi:
    def __init__(self):
        self.created = []
        self.replied = []
        self.next_create_response = FakeResponse()
        self.next_reply_response = FakeResponse()

    def create(self, request):
        self.created.append(request)
        return self.next_create_response

    def reply(self, request):
        self.replied.append(request)
        return self.next_reply_response


class FakeLarkClient:
    def __init__(self):
        self.message_api = RecordingMessageApi()
        self.im = types.SimpleNamespace(
            v1=types.SimpleNamespace(message=self.message_api)
        )


class Builder:
    def __init__(self):
        self.data = {}

    def receive_id_type(self, value):
        self.data["receive_id_type"] = value
        return self

    def receive_id(self, value):
        self.data["receive_id"] = value
        return self

    def message_id(self, value):
        self.data["message_id"] = value
        return self

    def request_body(self, value):
        self.data["request_body"] = value
        return self

    def msg_type(self, value):
        self.data["msg_type"] = value
        return self

    def content(self, value):
        self.data["content"] = value
        return self

    def app_id(self, value):
        self.data["app_id"] = value
        return self

    def app_secret(self, value):
        self.data["app_secret"] = value
        return self

    def register_p2_im_message_receive_v1(self, handler):
        self.data["message_handler"] = handler
        return self

    def build(self):
        return dict(self.data)


class FakeWSClient:
    instances = []

    def __init__(self, app_id, app_secret, event_handler, log_level):
        self.app_id = app_id
        self.app_secret = app_secret
        self.event_handler = event_handler
        self.log_level = log_level
        self.started = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True


def install_lark_stubs():
    lark = types.ModuleType("lark_oapi")
    lark.LogLevel = types.SimpleNamespace(DEBUG="debug")
    lark.EventDispatcherHandler = types.SimpleNamespace(
        builder=lambda token, secret: Builder()
    )
    lark.Client = types.SimpleNamespace(builder=lambda: Builder())
    lark.ws = types.SimpleNamespace(Client=FakeWSClient)

    model = types.ModuleType("lark_oapi.api.im.v1.model")
    model.CreateMessageRequest = types.SimpleNamespace(builder=lambda: Builder())
    model.CreateMessageRequestBody = types.SimpleNamespace(builder=lambda: Builder())
    model.ReplyMessageRequest = types.SimpleNamespace(builder=lambda: Builder())
    model.ReplyMessageRequestBody = types.SimpleNamespace(builder=lambda: Builder())

    processor = types.ModuleType("lark_oapi.api.im.v1.processor")
    processor.P2ImMessageReceiveV1 = object

    sys.modules["lark_oapi"] = lark
    sys.modules["lark_oapi.api"] = types.ModuleType("lark_oapi.api")
    sys.modules["lark_oapi.api.im"] = types.ModuleType("lark_oapi.api.im")
    sys.modules["lark_oapi.api.im.v1"] = types.ModuleType("lark_oapi.api.im.v1")
    sys.modules["lark_oapi.api.im.v1.model"] = model
    sys.modules["lark_oapi.api.im.v1.processor"] = processor


def install_agent_stub():
    agent_package = types.ModuleType("agent")
    agent_module = types.ModuleType("agent.agent")

    async def run_agent(prompt, user_id, session_id):
        return f"{prompt}:{user_id}:{session_id}"

    agent_module.run_agent = run_agent
    sys.modules["agent"] = agent_package
    sys.modules["agent.agent"] = agent_module


def load_lark_main(monkeypatch):
    install_lark_stubs()
    install_agent_stub()
    monkeypatch.setenv("LARK_APP_ID", "app-id")
    monkeypatch.setenv("LARK_APP_SECRET", "app-secret")

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv

    spec = importlib.util.spec_from_file_location("lark_bot_main_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.client = FakeLarkClient()
    return module


def make_event(
    *,
    message_type="text",
    content='{"text": "hello"}',
    chat_type=None,
    chat_id=None,
    message_id=None,
    user_id="user-1",
):
    message = types.SimpleNamespace(
        message_type=message_type,
        content=content,
        chat_type=chat_type,
        chat_id=chat_id,
        message_id=message_id,
    )
    sender = types.SimpleNamespace(
        sender_id=types.SimpleNamespace(user_id=user_id)
    )
    event = types.SimpleNamespace(message=message, sender=sender)
    return types.SimpleNamespace(event=event)


def test_send_text_message_creates_p2p_message(monkeypatch):
    module = load_lark_main(monkeypatch)
    data = make_event(chat_type="p2p", chat_id="chat-1")

    module.send_text_message(data, "hello lark")

    request = module.client.message_api.created[0]
    body = request["request_body"]
    assert request["receive_id_type"] == "chat_id"
    assert body["receive_id"] == "chat-1"
    assert body["msg_type"] == "text"
    assert json.loads(body["content"]) == {"text": "hello lark"}
    assert module.client.message_api.replied == []


def test_send_text_message_replies_when_message_id_is_available(monkeypatch):
    module = load_lark_main(monkeypatch)
    data = make_event(message_id="message-1")

    module.send_text_message(data, "reply text")

    request = module.client.message_api.replied[0]
    body = request["request_body"]
    assert request["message_id"] == "message-1"
    assert body["msg_type"] == "text"
    assert json.loads(body["content"]) == {"text": "reply text"}
    assert module.client.message_api.created == []


def test_send_text_message_raises_for_failed_create(monkeypatch):
    module = load_lark_main(monkeypatch)
    module.client.message_api.next_create_response = FakeResponse(
        ok=False,
        code=500,
        msg="create failed",
        log_id="log-create",
    )
    data = make_event(chat_type="p2p", chat_id="chat-1")

    with pytest.raises(Exception, match="client.im.v1.message.create failed"):
        module.send_text_message(data, "boom")


def test_send_text_message_raises_for_unroutable_event(monkeypatch):
    module = load_lark_main(monkeypatch)
    data = types.SimpleNamespace(event=types.SimpleNamespace(message=None))

    with pytest.raises(Exception, match="do_p2_im_message_receive_v1 failed"):
        module.send_text_message(data, "missing route")


def test_handle_agent_result_sends_task_result(monkeypatch):
    module = load_lark_main(monkeypatch)
    sent = []
    monkeypatch.setattr(module, "send_text_message", lambda data, content: sent.append(content))
    task = types.SimpleNamespace(result=lambda: "agent answer")

    module.handle_agent_result(object(), task)

    assert sent == ["agent answer"]


def test_do_p2_im_message_receive_sends_parse_error_for_non_text(monkeypatch):
    module = load_lark_main(monkeypatch)
    data = make_event(message_type="image", content=None, message_id="message-1")

    module.do_p2_im_message_receive_v1(data)

    body = module.client.message_api.replied[0]["request_body"]
    assert json.loads(body["content"]) == {
        "text": "Parse message failed, please send text message."
    }


def test_do_p2_im_message_receive_runs_agent_on_running_loop(monkeypatch):
    module = load_lark_main(monkeypatch)
    calls = []

    async def fake_run_agent(prompt, user_id, session_id):
        calls.append((prompt, user_id, session_id))
        return "done"

    monkeypatch.setattr(module, "run_agent", fake_run_agent)
    data = make_event(content='{"text": "ask"}', message_id="message-1", user_id="u-1")

    async def invoke():
        module.do_p2_im_message_receive_v1(data)
        await asyncio.sleep(0)

    asyncio.run(invoke())

    assert calls == [("ask", "u-1", "u-1")]
    body = module.client.message_api.replied[0]["request_body"]
    assert json.loads(body["content"]) == {"text": "done"}


def test_main_starts_ws_client(monkeypatch):
    module = load_lark_main(monkeypatch)

    module.main()

    assert module.wsClient.started is True
