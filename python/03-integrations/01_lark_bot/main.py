import asyncio
import json
import os

import lark_oapi as lark
from agent.agent import run_agent
from dotenv import load_dotenv
from lark_oapi.api.im.v1.model import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from lark_oapi.api.im.v1.processor import P2ImMessageReceiveV1

load_dotenv()

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")

assert LARK_APP_ID, "LARK_APP_ID cannot be empty"
assert LARK_APP_SECRET, "LARK_APP_SECRET cannot be empty"


def send_text_message(data: P2ImMessageReceiveV1, content: str):
    assert client, "lark client cannot be None"
    assert client.im, "lark im client cannot be None"

    content = json.dumps({"text": content})

    if (
        data.event
        and data.event.message
        and data.event.message.chat_type == "p2p"
        and data.event.message.chat_id
    ):
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )

        # Use send OpenAPI to send messages
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
        response = client.im.v1.message.create(request)

        if not response.success():
            raise Exception(
                f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
    elif data.event and data.event.message and data.event.message.message_id:
        request = (
            ReplyMessageRequest.builder()
            .message_id(data.event.message.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("text")
                .build()
            )
            .build()
        )

        # Reply to messages using send OpenAPI
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/reply
        response = client.im.v1.message.reply(request)
        if not response.success():
            raise Exception(
                f"client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
    else:
        raise Exception(f"do_p2_im_message_receive_v1 failed, event: {data}")


def handle_agent_result(data: P2ImMessageReceiveV1, task: asyncio.Task):
    try:
        result = task.result()
        print("agent result:", result)
    except Exception as e:
        print("run agent error:", e)

    send_text_message(data, result)


# Register event handler to handle received messages.
# https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    assert client, "lark client cannot be None"
    assert client.im, "lark im client cannot be None"

    res_content = ""
    if (
        data.event
        and data.event.message
        and data.event.message.message_type == "text"
        and data.event.message.content
    ):
        if data.event.sender and data.event.sender.sender_id:
            # parse user id
            sender_id = data.event.sender.sender_id.user_id
            session_id = sender_id

            # parse user message as prompt
            prompt = json.loads(data.event.message.content)["text"]

            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                task = loop.create_task(run_agent(prompt, sender_id, session_id))
                task.add_done_callback(lambda t: handle_agent_result(data, task))
                return
        else:
            res_content = "Parse message failed, please send text message."
    else:
        res_content = "Parse message failed, please send text message."

    send_text_message(data, res_content)


# Register event handler.
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)

# Create LarkClient object for requesting OpenAPI, and create LarkWSClient object for receiving events using long connection.
client = lark.Client.builder().app_id(LARK_APP_ID).app_secret(LARK_APP_SECRET).build()
wsClient = lark.ws.Client(
    LARK_APP_ID,
    LARK_APP_SECRET,
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)


def main():
    #  Start long connection and register event handler.
    wsClient.start()


if __name__ == "__main__":
    main()
