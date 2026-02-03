import os
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, render_template
from flask_socketio import SocketIO
import jwt
import httpx
from google.adk.events.event import Event
from pydantic import BaseModel, ValidationError
from veadk.integrations.ve_identity.utils import (
    get_function_call_auth_config,
    is_pending_auth_event,
)

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# ==========================================================================================
# BEGIN: 与智能体交互
# ==========================================================================================
agent_name = os.environ.get("AGENT_NAME", "默认智能体")
agent_endpoint = os.environ.get("AGENT_ENDPOINT", "")
assert agent_endpoint, "AGENT_ENDPOINT环境变量必须设置"

socketio = SocketIO(app, cors_allowed_origins="*")


class StreamingError(BaseModel):
    error: str
    error_type: str
    message: str


@socketio.on("send_message")
def handle_message(data):
    """Handle incoming messages via WebSocket"""
    session_id = data.get("session_id", "web_session")
    message = data.get("message", "")

    if not message:
        socketio.emit("error", {"message": "Message cannot be empty"})
        return

    # Emit typing indicator
    socketio.emit("typing", {"status": True})

    try:
        # Run SSE client and stream responses
        run_sse_client_stream(message, session_id, agent_endpoint)
    except httpx.ConnectError:
        socketio.emit(
            "error",
            {"message": "连接错误: 无法连接到服务器。请检查网络连接和API端点配置。"},
        )
    except httpx.HTTPStatusError as e:
        socketio.emit(
            "error", {"message": f"HTTP错误: {e.response.status_code} - {str(e)}"}
        )
    except Exception as e:
        socketio.emit("error", {"message": f"未知错误: {str(e)}"})
    finally:
        socketio.emit("typing", {"status": False})


def run_sse_client_stream(
    message: str, session_id: str = None, agent_endpoint: str = None
):
    """Run SSE client and stream events via WebSocket"""

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "session_id": session_id,
    }

    global access_token
    if access_token:
        claims = jwt.decode(access_token, options={"verify_signature": False})
        user_id = claims.get("sub", "")
        headers.update(
            {
                "user_id": user_id,
                "Authorization": f"Bearer {access_token}",
            }
        )
    else:
        user_id = "anonymous_user"
        headers.update(
            {
                "user_id": user_id,
            }
        )

    with httpx.Client(timeout=300, headers=headers) as client:
        url = f"{agent_endpoint}/invoke"
        body = {"prompt": message}

        with client.stream("POST", url, json=body, headers=headers) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type")
            if "application/json" in content_type:
                # no streaming
                response.read()
                text = response.json()
                socketio.emit("message_response", {"content": text, "type": "text"})
            elif "text/event-stream" in content_type:
                # streaming
                buffer = ""
                for chunk in response.iter_bytes():
                    try:
                        text = chunk.decode("utf-8")
                        buffer += text
                    except UnicodeDecodeError:
                        continue

                    # Parse SSE events
                    while "\n\n" in buffer:
                        event, buffer = buffer.split("\n\n", 1)
                        if event.startswith("data: "):
                            data_content = event[6:]
                            try:
                                # Try StreamingError first
                                try:
                                    parsed = StreamingError.model_validate_json(
                                        data_content
                                    )
                                    socketio.emit(
                                        "error",
                                        {
                                            "message": f"Error: {parsed.message}",
                                            "type": parsed.error_type,
                                        },
                                    )
                                    return
                                except ValidationError:
                                    # If not StreamingError, try Event
                                    parsed = Event.model_validate_json(data_content)

                                    # 异步授权事件
                                    if is_pending_auth_event(parsed):
                                        auth_config = get_function_call_auth_config(
                                            parsed
                                        )
                                        auth_uri = auth_config.exchanged_auth_credential.oauth2.auth_uri
                                        socketio.emit(
                                            "auth_required",
                                            {
                                                "message": f"Authentication required. Please visit: {auth_uri}",
                                                "auth_uri": auth_uri,
                                            },
                                        )

                                    # Stream text content
                                    for part in parsed.content.parts:
                                        if part.text:
                                            socketio.emit(
                                                "message_response",
                                                {"content": part.text, "type": "text"},
                                            )
                            except ValidationError:
                                # Emit raw event data for debugging
                                socketio.emit(
                                    "message_response",
                                    {"content": data_content, "type": "raw"},
                                )
                        else:
                            # Emit other events
                            socketio.emit(
                                "message_response", {"content": event, "type": "other"}
                            )
            else:
                socketio.emit(
                    "message_response",
                    {
                        "content": f'Unknown content type: "{content_type}"',
                        "type": "error",
                    },
                )


# ==========================================================================================
# END: 与智能体交互
# ==========================================================================================

# =====================================================================================================
# BEGIN：OAuth2登录相关代码，完成登录后会使用OAuth2 JWT来验证智能体
# =====================================================================================================
issuer = os.environ.get("OAUTH2_ISSUER_URI")
client_id = os.environ.get("OAUTH2_CLIENT_ID")
client_secret = os.environ.get("OAUTH2_CLIENT_SECRET")
redirect_uri = os.environ.get("OAUTH2_REDIRECT_URI", "http://127.0.0.1:8082/callback")
scopes = os.environ.get("OAUTH2_SCOPES", "openid profile email")
assert issuer is not None
assert client_id is not None
assert client_secret is not None

oauth = OAuth(app)
oauth.register(
    name="ciam",
    client_id=client_id,
    client_secret=client_secret,
    server_metadata_url=f"{issuer}/.well-known/openid-configuration",
    client_kwargs={"scope": scopes},
    redirect_uri=redirect_uri,
)

access_token = None


@app.route("/")
def index():
    """Chat interface page"""
    global access_token
    is_logged_in = False
    user_info = "ANONYMOUS"

    if access_token is not None:
        try:
            claims = jwt.decode(access_token, options={"verify_signature": False})
            user_info = claims.get("sub", "")
            is_logged_in = True
        except jwt.DecodeError:
            access_token = None

    return render_template(
        "index.html",
        is_logged_in=is_logged_in,
        user_info=user_info,
        agent_name=agent_name,
    )


@app.get("/login")
def login():
    return oauth.ciam.authorize_redirect(redirect_uri=redirect_uri)


@app.get("/callback")
def callback():
    global access_token
    access_token = oauth.ciam.authorize_access_token().get("access_token")
    return redirect("/")


@app.get("/logout")
def logout():
    global access_token
    access_token = None
    return redirect("/")


# =====================================================================================================
# END：OAuth2登录相关代码，完成登录后会使用OAuth2 JWT来验证智能体
# =====================================================================================================

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=8082, debug=True)
