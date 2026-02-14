import asyncio
from concurrent.futures import Future
import json
import logging
import os
import threading

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from lark_oapi.api.im.v1 import ReplyMessageRequest
from lark_oapi.api.im.v1 import ReplyMessageRequestBody
from lark_oapi.ws import Client as WSClient

import uvicorn
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from veadk import Runner
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.lite_llm import LiteLlm

# Import Producer Agent
from agent import APP_NAME, producer_agent

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LARK_APP_ID = os.environ.get("LARK_APP_ID")
LARK_APP_SECRET = os.environ.get("LARK_APP_SECRET")
LARK_ENCRYPT_KEY = os.environ.get("LARK_ENCRYPT_KEY", "")
LARK_VERIFICATION_TOKEN = os.environ.get("LARK_VERIFICATION_TOKEN", "")

lark_http_client = None
if LARK_APP_ID and LARK_APP_SECRET:
    lark_http_client = (
        lark.Client.builder()
        .app_id(LARK_APP_ID)
        .app_secret(LARK_APP_SECRET)
        .log_level(lark.LogLevel.INFO)
        .build()
    )

processed_events = set()
events_lock = threading.Lock()

agent_loop = None
runner = None
agent_ready = threading.Event()

async def run_agent(prompt: str, user_id: str, session_id: str) -> str:
    logger.info(
        "run_agent: user_id=%s session_id=%s prompt_len=%s",
        user_id,
        session_id,
        len(prompt) if prompt is not None else 0,
    )
    return await runner.run(prompt, user_id, session_id)


def _reply_text(message_id: str, text: str) -> None:
    if not lark_http_client:
        return
    if not text or not text.strip():
        text = "（无内容回复）"

    req = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .content(json.dumps({"text": text}))
            .msg_type("text")
            .build()
        )
        .build()
    )
    resp = lark_http_client.im.v1.message.reply(req)
    if not resp.success():
        logger.error(f"Failed to reply to Lark: {resp.code} - {resp.msg}")


def _handle_agent_result(future: Future, message_id: str):
    try:
        result = future.result()
        logger.info(f"Agent finished execution. Result length: {len(result) if result else 0}")
    except Exception as e:
        logger.error(f"Agent execution failed with exception: {e}", exc_info=True)
        result = "（处理失败，请查看后台日志）"
    
    try:
        _reply_text(message_id, result)
    except Exception as e:
        logger.error(f"Failed to send reply to Lark: {e}", exc_info=True)


def handle_message(data: P2ImMessageReceiveV1):
    try:
        event_id = data.header.event_id
        with events_lock:
            if event_id in processed_events:
                return
            processed_events.add(event_id)
            if len(processed_events) > 10000:
                processed_events.clear()

        message = data.event.message
        if message.message_type != "text":
            return

        try:
            content_dict = json.loads(message.content or "{}")
        except Exception:
            return

        text = content_dict.get("text", "")
        if not text:
            return

        if not agent_ready.is_set():
            logger.error("Agent runner is not ready.")
            return

        sender_id = data.event.sender.sender_id.open_id
        session_id = message.chat_id
        message_id = message.message_id

        future: Future = asyncio.run_coroutine_threadsafe(
            run_agent(text, sender_id, session_id),
            agent_loop,
        )
        # Use callback instead of blocking wait
        future.add_done_callback(
            lambda f: _handle_agent_result(f, message_id)
        )
    except Exception as e:
        logger.error(f"Error handling Lark message: {e}")

def get_compaction_instruction():
    # 简化的 Compaction Instruction，用于压缩历史记忆
    return """
    You are an expert summarizer. Your goal is to summarize the conversation history between a user and an AI Movie Producer.
    Preserve key details about:
    1. The user's creative preferences (style, genre, characters).
    2. The current status of the movie project (scripting, filming, or reviewing).
    3. Any specific decisions made (e.g., "The cat is a cyberpunk hacker").
    Discard trivial chitchat.
    """

def start_agent_executor() -> None:
    global agent_loop, runner
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    local_agent = producer_agent
    
    # 确保 Memory 已初始化
    short_term_memory = getattr(local_agent, "short_term_memory", None)
    
    runner = Runner(
        agent=local_agent,
        short_term_memory=short_term_memory,
        app_name=APP_NAME,
    )
    
    # 配置 App 和 Memory Compaction
    runner.app = App(
        name=APP_NAME,
        root_agent=local_agent,
        events_compaction_config=EventsCompactionConfig(
            summarizer=LlmEventSummarizer(
                llm=LiteLlm(
                    model=os.getenv(
                        "EVENTS_COMPACTION_MODEL",
                        "openai/doubao-seed-1-6-lite-251015",
                    ),
                    api_base=os.getenv(
                        "EVENTS_COMPACTION_API_BASE",
                        "https://ark.cn-beijing.volces.com/api/v3/",
                    ),
                    api_key=os.getenv("EVENTS_COMPACTION_API_KEY", os.getenv("MODEL_AGENT_API_KEY", "")),
                ),
                prompt_template=get_compaction_instruction(),
            ),
            compaction_interval=int(os.getenv("EVENTS_COMPACTION_INTERVAL", "5")), # 稍微放宽一点
            overlap_size=int(os.getenv("EVENTS_COMPACTION_OVERLAP_SIZE", "2")),
        ),
    )
    agent_loop = loop
    agent_ready.set()
    logger.info("Agent Executor started and ready.")
    loop.run_forever()


def start_lark_ws_client() -> None:
    if not (LARK_APP_ID and LARK_APP_SECRET):
        logger.warning("Missing LARK_APP_ID or LARK_APP_SECRET. Lark client will not start.")
        return

    logger.info(f"Starting Lark WS Client for App ID: {LARK_APP_ID}")
    ws_client = WSClient(
        LARK_APP_ID,
        LARK_APP_SECRET,
        event_handler=(
            lark.EventDispatcherHandler.builder(LARK_ENCRYPT_KEY, LARK_VERIFICATION_TOKEN)
            .register_p2_im_message_receive_v1(handle_message)
            .build()
        ),
        log_level=lark.LogLevel.INFO,
    )
    ws_client.start()


async def ping(_: object) -> PlainTextResponse:
    return PlainTextResponse("pong")


async def health(_: object) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def readiness(_: object) -> PlainTextResponse:
    if agent_ready.is_set():
        return PlainTextResponse("ready")
    return PlainTextResponse("not ready", status_code=503)


async def liveness(_: object) -> PlainTextResponse:
    return PlainTextResponse("alive")


async def on_startup() -> None:
    agent_thread = threading.Thread(target=start_agent_executor, daemon=True)
    agent_thread.start()

    ws_thread = threading.Thread(target=start_lark_ws_client, daemon=True)
    ws_thread.start()


def main() -> None:
    app = Starlette(
        routes=[
            Route("/ping", ping, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
            Route("/readiness", readiness, methods=["GET"]),
            Route("/liveness", liveness, methods=["GET"]),
        ],
        on_startup=[on_startup],
    )
    # 默认 8000 端口，可配置
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
