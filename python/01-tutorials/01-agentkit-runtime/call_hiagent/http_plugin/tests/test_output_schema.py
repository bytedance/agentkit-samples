import json
import unittest
from unittest.mock import patch

import httpx

from plugin_response import json_reply, sse_frames
from plugin_server import app


class OutputSchemaTest(unittest.IsolatedAsyncioTestCase):
    async def test_json_reply_contains_only_the_output_string(self):
        body = {
            "message": "介绍你自己",
            "session_id": "1",
            "user_id": "123",
            "streaming": False,
        }
        text = "我是 Agentkit-01。"
        event = {"content": {"role": "model", "parts": [{"text": text}]}}

        def runtime(request):
            path = request.url.path
            if "/sessions/" in path:
                self.assertTrue(path.endswith("/users/123/sessions/1"))
                return httpx.Response(200, json={})
            if path == "/invoke":
                self.assertEqual(request.headers["user_id"], "123")
                self.assertEqual(request.headers["session_id"], "1")
            else:
                payload = json.loads(request.content)
                self.assertEqual(
                    (payload["user_id"], payload["session_id"]), ("123", "1")
                )
            if path == "/run":
                return httpx.Response(200, json=[event])
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                text=f"data: {json.dumps(event)}\n\n",
            )

        remote = httpx.AsyncClient(
            transport=httpx.MockTransport(runtime),
            base_url="http://runtime.test",
            headers={"Authorization": "Bearer test"},
        )
        with patch("plugin_server.runtime_client", return_value=remote):
            async with (
                app.router.lifespan_context(app),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app), base_url="http://plugin.test"
                ) as client,
            ):
                for path in ("/", "/invoke", "/run", "/run_sse"):
                    with self.subTest(path=path):
                        response = await client.post(path, json=body)
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json(), {"output": text})

    async def test_stream_ends_with_error_when_final_text_revises_a_chunk(self):
        events = [
            {"partial": True, "content": {"parts": [{"text": "你好"}]}},
            {"content": {"parts": [{"text": "您好"}]}},
        ]
        reply = await json_reply(httpx.Response(200, json=events))
        self.assertEqual(reply.output, "您好")

        frames = [frame async for frame in sse_frames(httpx.Response(200, json=events))]
        self.assertEqual(len(frames), 2)
        self.assertIn('"content": "你好"', frames[0])
        self.assertTrue(frames[1].startswith("event: error\n"))
