import os
import re
import uuid
import base64
import logging
import tos
import importlib
from pathlib import Path
from typing import Any, Optional, Tuple, List

from veadk.knowledgebase import KnowledgeBase
from veadk.memory import LongTermMemory, ShortTermMemory
from veadk.prompts.prompt_manager import CozeloopPromptManager
from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer
from veadk.tracing.telemetry.exporters.apmplus_exporter import APMPlusExporter
from veadk.tracing.telemetry.exporters.cozeloop_exporter import CozeloopExporter
from veadk.tracing.telemetry.exporters.tls_exporter import TLSExporter
from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_LABEL = "beta"

def init_short_term_memory(app_name: str) -> Optional[ShortTermMemory]:
    if os.getenv("DATABASE_POSTGRESQL_HOST"):
        return ShortTermMemory(backend="postgresql")
    return ShortTermMemory(backend="local")

def init_knowledge_base(app_name: str) -> Optional[KnowledgeBase]:
    kb_collection = os.getenv("DATABASE_VIKING_COLLECTION_NAME")
    if kb_collection:
        return KnowledgeBase(backend="viking", index=kb_collection, app_name=app_name)
    return None

def init_long_term_memory(app_name: str) -> Optional[LongTermMemory]:
    # 复用 Shared Memory 以获取用户画像
    try:
        return LongTermMemory(
            backend="viking_mem", 
            index=os.getenv("DATABASE_VIKING_MEM_COLLECTION_NAME", "volcagent_shared_memory"),
            app_name=app_name
        )
    except Exception as e:
        logger.warning(f"Failed to initialize LongTermMemory: {e}")
        return None


def init_prompt_manager() -> Optional[CozeloopPromptManager]:
    if not CozeloopPromptManager:
        return None
    prompt_key = os.getenv("PROMPT_MANAGEMENT_COZELOOP_PROMPT_KEY")
    if not prompt_key:
        return None
    try:
        manager = CozeloopPromptManager(
            cozeloop_workspace_id=os.getenv("PROMPT_MANAGEMENT_COZELOOP_WORKSPACE_ID", ""),
            cozeloop_token=os.getenv("PROMPT_MANAGEMENT_COZELOOP_TOKEN", ""),
            prompt_key=prompt_key,
            label=os.getenv("PROMPT_MANAGEMENT_COZELOOP_LABEL", DEFAULT_PROMPT_LABEL),
        )
        # 尝试验证连接（可选，或者直接返回让 Agent 处理异常，但在初始化阶段捕获更好）
        # 这里假设如果 token 错误，后续调用才会失败。
        # 但如果是初始化报错，应该捕获。
        return manager
    except Exception as e:
        logger.warning(f"Failed to initialize CozeloopPromptManager: {e}. Fallback to local instruction.")
        return None


def init_observability() -> List[OpentelemetryTracer]:
    exporters = []
    if os.getenv("OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT") and APMPlusExporter:
        exporters.append(APMPlusExporter())
    if os.getenv("OBSERVABILITY_OPENTELEMETRY_COZELOOP_ENDPOINT") and CozeloopExporter:
        exporters.append(CozeloopExporter())
    if os.getenv("OBSERVABILITY_OPENTELEMETRY_TLS_ENDPOINT") and TLSExporter:
        exporters.append(TLSExporter())
    return [OpentelemetryTracer(exporters=exporters)] if exporters else []


def load_local_instruction(instruction_path: str) -> Optional[str]:
    path = Path(instruction_path)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


async def callback_cleanup_model_output(callback_context: CallbackContext, llm_response):
    if llm_response and llm_response.content and llm_response.content.parts:
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

            if part.text:
                cleaned_text = re.sub(
                    r"<thought>.*?</thought>", "", part.text, flags=re.DOTALL
                )
                answer_match = re.search(
                    r"<answer>(.*?)</answer>", cleaned_text, flags=re.DOTALL
                )
                part.text = (answer_match.group(1) if answer_match else cleaned_text).strip()

            has_text = bool(part.text and part.text.strip())
            has_function = hasattr(part, "function_call") and part.function_call
            if has_text or has_function:
                clean_parts.append(part)
        llm_response.content.parts = clean_parts
    return llm_response

def get_tos_client():
    ak = os.getenv("VOLCENGINE_ACCESS_KEY")
    sk = os.getenv("VOLCENGINE_SECRET_KEY")
    endpoint = os.getenv("DATABASE_TOS_ENDPOINT", "tos-cn-beijing.volces.com")
    region = os.getenv("DATABASE_TOS_REGION", "cn-beijing")
    
    if not ak or not sk:
        logger.error("Missing VOLCENGINE_ACCESS_KEY or VOLCENGINE_SECRET_KEY")
        return None
        
    return tos.TosClientV2(ak, sk, endpoint, region)

def upload_bytes_to_tos(data_bytes, extension=".png"):
    bucket = os.getenv("DATABASE_TOS_BUCKET")
    if not bucket:
        return None, "Missing DATABASE_TOS_BUCKET env var"

    client = get_tos_client()
    if not client:
        return None, "Failed to initialize TOS client (Missing AK/SK)"

    key = f"agent_uploads/{uuid.uuid4()}{extension}"
    
    try:
        client.put_object(bucket, key, content=data_bytes)
        
        # Generate Pre-signed URL (valid for 1 hour)
        url = client.pre_signed_url(
            http_method='GET',
            bucket=bucket,
            key=key,
            expires=3600
        )
        return url, None
    except Exception as e:
        error_msg = f"Failed to upload to TOS: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

def upload_base64_to_tos(base64_str):
    try:
        # 1. Try to find data URI pattern
        data_uri_pattern = re.compile(r'data:image/(?P<ext>png|jpeg|jpg|gif|bmp|webp);base64,(?P<data>[A-Za-z0-9+/=]+)')
        match = data_uri_pattern.search(base64_str)
        
        if match:
            extension = f".{match.group('ext')}"
            data = match.group('data')
        else:
            # 2. No data URI, assume raw base64 or raw long text
            try:
                base64_str.encode('ascii')
            except UnicodeEncodeError:
                return None, None 
            
            data = base64_str.strip().replace("\n", "").replace("\r", "").replace(" ", "")
            extension = ".png" # Default assumption

        data_bytes = base64.b64decode(data, validate=True)
        return upload_bytes_to_tos(data_bytes, extension)
    except Exception as e:
        error_msg = f"Failed to decode base64: {str(e)}"
        logger.warning(error_msg) 
        return None, error_msg

async def callback_cleanup_tool_output(tool, args: dict[str, Any], tool_context, tool_response: dict) -> Optional[dict]:
    """
    Callback to sanitize tool outputs.
    Finds base64 images in text, uploads them to TOS, and replaces them with URLs.
    """
    if not tool_response:
        return tool_response

    def clean_data(data):
        if isinstance(data, dict):
            return {k: clean_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [clean_data(v) for v in data]
        elif isinstance(data, str):
            # Regex to find data URI: data:image/<ext>;base64,<data>
            pattern = r'(data:image/(?:png|jpeg|jpg|gif|bmp|webp);base64,([A-Za-z0-9+/=\s]+))'
            
            # Find all matches
            matches = list(re.finditer(pattern, data))
            
            new_data = data
            
            if matches:
                # Replace from end to start to avoid index shifting
                for match in reversed(matches):
                    full_match = match.group(1)
                    base64_content = match.group(2)
                    
                    if len(base64_content) > 1000: 
                        url, error = upload_base64_to_tos(full_match)
                        
                        replacement = ""
                        if url:
                            replacement = f"[IMAGE_UPLOADED_TO_TOS: {url}]"
                        else:
                            replacement = f"[UPLOAD_FAILED: {error} | TRUNCATED_IMAGE]"
                            
                        start, end = match.span()
                        new_data = new_data[:start] + replacement + new_data[end:]
            
            if len(new_data) > 20000:
                logger.warning(f"Tool output too long ({len(new_data)} chars), truncating...")
                head = new_data[:5000]
                tail = new_data[-5000:]
                new_data = f"{head}\n\n[... {len(new_data) - 10000} characters of logs truncated ...]\n\n{tail}"
            
            return new_data
        else:
            return data

    return clean_data(tool_response)


def init_veadk_builtin_tools() -> List[Any]:
    """
    根据环境变量 VEADK_BUILTIN_TOOLS_ENABLE 加载 veadk 内置工具。
    默认启用: web_search
    """
    # 默认启用 web_search (如果条件满足)
    default_tools = "web_search"
    enabled_tools_str = os.getenv("VEADK_BUILTIN_TOOLS_ENABLE", default_tools)
    tool_names = [t.strip() for t in enabled_tools_str.split(",") if t.strip()]
    
    tools = []
    for name in tool_names:
        # execute_skills 需要 AGENTKIT_TOOL_ID
        if name == "execute_skills" and not os.getenv("AGENTKIT_TOOL_ID"):
            continue

        try:
            # 动态导入: veadk.tools.builtin_tools.<name>
            module_path = f"veadk.tools.builtin_tools.{name}"
            module = importlib.import_module(module_path)
            
            # 获取同名对象
            tool = getattr(module, name)
            
            if tool:
                tools.append(tool)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Failed to load builtin tool '{name}': {e}")
            continue
            
    return tools
