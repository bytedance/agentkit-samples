import streamlit as st
import os
import json
import time
import httpx
import requests
import asyncio
import random

# --- 页面配置 ---
st.set_page_config(
    page_title="SQL Talk Pro",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Agent 服务配置 ---
LOCAL_AGENT_URL = "http://127.0.0.1:8000"
REMOTE_AGENT_URL = os.getenv("API_GATEWAY_URL", "")
API_KEY = os.getenv("API_GATEWAY_API_KEY", "")
APP_NAME = "data_analysis_with_code"
USER_ID = "A2A_USER_"


def get_session_id():
    return f"agentkit_sample_session_{random.randint(1, 999999)}"


# --- 会话状态初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent_session_id" not in st.session_state:
    st.session_state.agent_session_id = None
if "use_remote" not in st.session_state:
    st.session_state.use_remote = True
if "api_key" not in st.session_state:
    st.session_state.api_key = API_KEY
if "agent_base_url_input" not in st.session_state:
    st.session_state.agent_base_url_input = ""
if "a2a_timeout_secs" not in st.session_state:
    st.session_state.a2a_timeout_secs = int(os.getenv("A2A_TIMEOUT_SECS", "600"))


# --- Helper Functions ---
def get_headers():
    """根据是否连接远程服务返回请求头"""
    if st.session_state.use_remote:
        key = (st.session_state.api_key or "").strip()
        if key:
            return {"Authorization": f"Bearer {key}"}
    return {}


def get_full_base_url():
    return (
        st.session_state.agent_base_url_input
        or (REMOTE_AGENT_URL if st.session_state.use_remote else LOCAL_AGENT_URL)
    ).rstrip("/")


def create_agent_session():
    """创建新的会话ID"""
    session_id = f"st-pro-session-{int(time.time())}"
    st.session_state.agent_session_id = session_id
    st.toast(f"✅ 新会话已创建: {session_id}", icon="🎉")


def probe_agent_card():
    """探测Agent服务是否可用"""
    base = get_full_base_url()
    for url in [f"{base}/.well-known/agent-card.json", f"{base}/agent_card"]:
        try:
            r = requests.get(url, headers=get_headers(), timeout=15)
            if r.ok:
                st.success("Agent Card 可用")
                try:
                    st.json(r.json())
                except Exception:
                    st.code(r.text)
                return True
        except Exception as e:
            st.warning(f"探测失败 {url}: {e}")
    st.error("未找到 Agent Card 端点，请检查网关前缀或鉴权配置。")
    return False


async def send_via_http(message: str) -> str:
    """通过HTTP协议发送消息"""
    base = get_full_base_url()
    auth_headers = get_headers()
    if st.session_state.use_remote and not auth_headers:
        raise RuntimeError(
            "缺少 API Key。请在侧边栏填写或设置环境变量 API_GATEWAY_API_KEY"
        )

    # 使用应用程序会话ID
    session_id = st.session_state.agent_session_id
    full_text = ""

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=30, read=120, write=30)
        ) as client:
            # Step 1: Create session if not already created
            session_url = (
                f"{base}/apps/{APP_NAME}/users/{USER_ID}/sessions/{session_id}"
            )
            _session_resp = await client.post(session_url, headers=auth_headers)
            # 忽略会话创建失败，可能服务器不需要显式创建

            # Step 2: Send message
            request_body = {
                "app_name": APP_NAME,
                "user_id": USER_ID,
                "session_id": session_id,
                "new_message": {"parts": [{"text": message}], "role": "user"},
                "stream": True,
            }

            async with client.stream(
                "POST", f"{base}/run_sse", json=request_body, headers=auth_headers
            ) as r:
                async for line in r.aiter_lines():
                    if line:
                        # 解析服务器发送的事件
                        line = line.strip()
                        if line.startswith("data: "):
                            data = line[6:]
                            try:
                                json_data = json.loads(data)
                                # 提取文本内容
                                task_data = json_data.get("task", json_data)
                                if "content" in task_data:
                                    content = task_data["content"]
                                    if "parts" in content:
                                        for part in content["parts"]:
                                            if "text" in part:
                                                full_text += part["text"]
                                            elif "functionCall" in part:
                                                # 跳过函数调用，仅显示文本
                                                pass
                                            elif "functionResponse" in part:
                                                # 跳过函数响应，仅显示文本
                                                pass
                                            elif (
                                                "root" in part
                                                and "text" in part["root"]
                                            ):
                                                full_text += part["root"]["text"]
                                elif "artifacts" in task_data:
                                    for artifact in task_data["artifacts"]:
                                        if "parts" in artifact:
                                            for part in artifact["parts"]:
                                                if (
                                                    "root" in part
                                                    and "text" in part["root"]
                                                ):
                                                    full_text += part["root"]["text"]
                                elif "text" in task_data:
                                    full_text += task_data["text"]
                                elif "content" in json_data:
                                    # 处理直接在json根目录的content
                                    content = json_data["content"]
                                    if "parts" in content:
                                        for part in content["parts"]:
                                            if "text" in part:
                                                full_text += part["text"]
                                            elif (
                                                "root" in part
                                                and "text" in part["root"]
                                            ):
                                                full_text += part["root"]["text"]
                            except json.JSONDecodeError:
                                # 非JSON响应直接追加
                                full_text += data
    except Exception as e:
        full_text = f"发生错误: {str(e)}"
        import traceback

        traceback.print_exc()

    # 清理响应格式
    full_text = (
        full_text.strip().replace("\r", "\n").replace("\n", "\n").replace("\t", "    ")
    )
    return full_text


# --- 侧边栏 UI ---
with st.sidebar:
    st.title("✨ SQL Talk Pro")
    st.markdown("与您的数据进行智能对话")

    st.divider()

    # 连接模式切换
    st.session_state.use_remote = st.toggle(
        "连接远程 Agent",
        value=st.session_state.use_remote,
        help="切换连接本地或远程部署的 Agent 服务",
    )

    # Agent 基地址
    default_url = REMOTE_AGENT_URL if st.session_state.use_remote else LOCAL_AGENT_URL
    st.session_state.agent_base_url_input = st.text_input(
        "Agent 基地址", value=st.session_state.agent_base_url_input or default_url
    )

    # API Key
    if st.session_state.use_remote:
        st.session_state.api_key = st.text_input(
            "API Key", value=st.session_state.api_key, type="password"
        )

    # 请求超时
    st.session_state.a2a_timeout_secs = st.number_input(
        "请求超时秒数",
        min_value=60,
        max_value=3600,
        value=st.session_state.a2a_timeout_secs,
        step=30,
        help="长查询建议 600-1200 秒",
    )

    st.info(f"当前连接: `{get_full_base_url()}`")

    # 创建新会话
    if st.button("创建新会话", use_container_width=True):
        create_agent_session()

    # 探测Agent Card
    if st.button("探测 Agent Card", use_container_width=True):
        probe_agent_card()

# --- 主聊天界面 ---
st.header("对话窗口")

if not st.session_state.agent_session_id:
    st.info("👈 请在左侧边栏配置连接模式，然后点击“创建新会话”开始对话。")
    st.stop()

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        try:
            obj = json.loads(msg["content"])
            st.json(obj)
        except Exception:
            st.code(msg["content"])

# 处理用户输入
if prompt := st.chat_input("请输入您的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # 使用 HTTP 客户端发送消息
        try:
            with st.spinner("思考中..."):
                full_response = asyncio.run(send_via_http(prompt))

                # 显示响应
                st.markdown(full_response)

                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )
        except Exception as e:
            st.error(f"发生错误: {e}")
            import traceback

            traceback.print_exc()
