import os
import uuid
import base64
import logging
import re
import importlib
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def get_tos_client():
    ak = os.getenv("VOLCENGINE_ACCESS_KEY")
    sk = os.getenv("VOLCENGINE_SECRET_KEY")
    endpoint = os.getenv("DATABASE_TOS_ENDPOINT", "tos-cn-beijing.volces.com")
    region = os.getenv("DATABASE_TOS_REGION", "cn-beijing")
    if not ak or not sk:
        return None
    try:
        import tos
    except Exception:
        return None
    return tos.TosClientV2(ak, sk, endpoint, region)


def upload_bytes_to_tos(data_bytes: bytes, extension: str = ".png"):
    bucket = os.getenv("DATABASE_TOS_BUCKET")
    if not bucket:
        return None, "Missing DATABASE_TOS_BUCKET env var"

    client = get_tos_client()
    if not client:
        return None, "Failed to initialize TOS client"

    key = f"agent_uploads/{uuid.uuid4()}{extension}"
    try:
        client.put_object(bucket, key, content=data_bytes)
        url = client.pre_signed_url(
            http_method="GET",
            bucket=bucket,
            key=key,
            expires=3600,
        )
        return url, None
    except Exception as e:
        return None, f"Failed to upload to TOS: {str(e)}"


def upload_base64_to_tos(base64_str: str):
    try:
        data_uri_pattern = re.compile(
            r"data:image/(?P<ext>png|jpeg|jpg|gif|bmp|webp);base64,(?P<data>[A-Za-z0-9+/=]+)"
        )
        match = data_uri_pattern.search(base64_str)
        if match:
            extension = f".{match.group('ext')}"
            data = match.group("data")
        else:
            try:
                base64_str.encode("ascii")
            except UnicodeEncodeError:
                return None, None
            data = base64_str.strip().replace("\n", "").replace("\r", "").replace(" ", "")
            extension = ".png"

        data_bytes = base64.b64decode(data, validate=True)
        return upload_bytes_to_tos(data_bytes, extension)
    except Exception as e:
        return None, f"Failed to decode base64: {str(e)}"


def optional_symbol(module_path: str, symbol: str):
    try:
        module = importlib.import_module(module_path)
        return getattr(module, symbol)
    except Exception:
        return None


def init_veadk_builtin_tools():
    enabled = os.getenv("VEADK_BUILTIN_TOOLS_ENABLE", "").strip()
    enabled_set = {t.strip() for t in enabled.split(",") if t.strip()} if enabled else set()

    tool_defs = [
        ("web_search", "veadk.tools.builtin_tools.web_search", "web_search"),
        ("execute_skills", "veadk.tools.builtin_tools.execute_skills", "execute_skills"),
        ("mcp_router", "veadk.tools.builtin_tools.mcp_router", "mcp_router"),
        ("image_generate", "veadk.tools.builtin_tools.image_generate", "image_generate"),
    ]

    tools = []
    for tool_id, module_path, symbol in tool_defs:
        if enabled_set and tool_id not in enabled_set:
            continue
        tool = optional_symbol(module_path, symbol)
        if tool:
            tools.append(tool)

    return tools


def init_short_term_memory(app_name: str):
    from veadk.memory import ShortTermMemory

    if os.getenv("DATABASE_POSTGRESQL_HOST"):
        return ShortTermMemory(backend="postgresql")
    return ShortTermMemory(backend="local")


def init_long_term_memory(app_name: str):
    from veadk.memory import LongTermMemory

    mem_collection = os.getenv("DATABASE_VIKING_MEM_COLLECTION_NAME")
    if not mem_collection:
        return None
    return LongTermMemory(
        backend="viking_mem",
        index=mem_collection,
        app_name=app_name,
    )


def init_knowledge_base(app_name: str):
    from veadk.knowledgebase import KnowledgeBase

    kb_collection = os.getenv("DATABASE_VIKING_COLLECTION_NAME")
    if not kb_collection:
        return None
    return KnowledgeBase(backend="viking", index=kb_collection, app_name=app_name)


def init_prompt_manager(default_label: str = "beta"):
    try:
        from veadk.prompts.prompt_manager import CozeloopPromptManager
    except Exception:
        return None

    prompt_key = os.getenv("PROMPT_MANAGEMENT_COZELOOP_PROMPT_KEY")
    token = os.getenv("PROMPT_MANAGEMENT_COZELOOP_TOKEN")
    if not prompt_key or not token:
        return None
    return CozeloopPromptManager(
        cozeloop_workspace_id=os.getenv("PROMPT_MANAGEMENT_COZELOOP_WORKSPACE_ID", ""),
        cozeloop_token=token,
        prompt_key=prompt_key,
        label=os.getenv("PROMPT_MANAGEMENT_COZELOOP_LABEL", default_label),
    )


def init_observability():
    exporters = []
    try:
        from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer
        from veadk.tracing.telemetry.exporters.apmplus_exporter import APMPlusExporter
        from veadk.tracing.telemetry.exporters.cozeloop_exporter import CozeloopExporter
        from veadk.tracing.telemetry.exporters.tls_exporter import TLSExporter
    except Exception:
        return []

    if os.getenv("OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT") and APMPlusExporter:
        exporters.append(APMPlusExporter())
    if os.getenv("OBSERVABILITY_OPENTELEMETRY_COZELOOP_ENDPOINT") and CozeloopExporter:
        exporters.append(CozeloopExporter())
    if os.getenv("OBSERVABILITY_OPENTELEMETRY_TLS_ENDPOINT") and TLSExporter:
        exporters.append(TLSExporter())
    return [OpentelemetryTracer(exporters=exporters)] if exporters else []


def load_local_instruction(instruction_path: Path) -> Optional[str]:
    try:
        if instruction_path.exists():
            return instruction_path.read_text(encoding="utf-8")
    except Exception:
        return None
    return None


async def callback_cleanup_model_output(callback_context: Any, llm_response: Any):
    if llm_response and getattr(llm_response, "content", None) and getattr(llm_response.content, "parts", None):
        clean_parts = []
        for part in llm_response.content.parts:
            is_thought = False
            try:
                if hasattr(part, "thought") and part.thought:
                    is_thought = True
                elif hasattr(part, "to_dict") and part.to_dict().get("thought"):
                    is_thought = True
            except Exception:
                pass
            if is_thought:
                continue

            if getattr(part, "text", None):
                cleaned_text = re.sub(r"<thought>.*?</thought>", "", part.text, flags=re.DOTALL)
                answer_match = re.search(r"<answer>(.*?)</answer>", cleaned_text, flags=re.DOTALL)
                part.text = (answer_match.group(1) if answer_match else cleaned_text).strip()

            has_text = bool(getattr(part, "text", None) and part.text.strip())
            has_function = hasattr(part, "function_call") and part.function_call
            if has_text or has_function:
                clean_parts.append(part)
        llm_response.content.parts = clean_parts
    return llm_response


async def callback_cleanup_tool_output(
    tool: Any, args: dict[str, Any], tool_context: Any, tool_response: dict
) -> Optional[dict]:
    if not tool_response:
        return tool_response

    def clean_data(data):
        if isinstance(data, dict):
            return {k: clean_data(v) for k, v in data.items()}
        if isinstance(data, list):
            return [clean_data(v) for v in data]
        if isinstance(data, str):
            pattern = r"(data:image/(?:png|jpeg|jpg|gif|bmp|webp);base64,([A-Za-z0-9+/=\s]+))"
            matches = list(re.finditer(pattern, data))
            new_data = data
            if matches:
                for match in reversed(matches):
                    full_match = match.group(1)
                    base64_content = match.group(2)
                    if len(base64_content) > 1000:
                        url, error = upload_base64_to_tos(full_match)
                        replacement = f"[IMAGE_UPLOADED_TO_TOS: {url}]" if url else f"[UPLOAD_FAILED: {error}]"
                        start, end = match.span()
                        new_data = new_data[:start] + replacement + new_data[end:]
            if len(new_data) > 20000:
                head = new_data[:5000]
                tail = new_data[-5000:]
                new_data = f"{head}\n\n[... {len(new_data) - 10000} characters of logs truncated ...]\n\n{tail}"
            return new_data
        return data

    return clean_data(tool_response)
