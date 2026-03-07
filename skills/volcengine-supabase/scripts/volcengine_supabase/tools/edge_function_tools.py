from typing import Optional, List
import logging
import json
import html
import os
import re
from urllib.parse import quote
from .base import BaseTools
from ..utils import handle_errors, read_only_check
from ..models import EdgeFunction
from ..platform.supabase_client import SupabaseApiError

logger = logging.getLogger(__name__)

# 运行时配置
RUNTIME_CONFIG = {
    "native-node20/v1": {
        "entrypoint": "index.ts",
        "extensions": [".ts", ".js"],
        "description": "Node.js 20 runtime"
    },
    "native-python3.9/v1": {
        "entrypoint": "app.py",
        "extensions": [".py"],
        "description": "Python 3.9 runtime"
    },
    "native-python3.10/v1": {
        "entrypoint": "app.py",
        "extensions": [".py"],
        "description": "Python 3.10 runtime"
    },
    "native-python3.12/v1": {
        "entrypoint": "app.py",
        "extensions": [".py"],
        "description": "Python 3.12 runtime"
    }
}

# 保留的函数名
RESERVED_SLUGS = {"deploy", "body", "health", "metrics"}
MAX_SLUG_LENGTH = 127
MAX_CODE_SIZE = 10 * 1024 * 1024  # 10MB
WORKSPACE_SLUG = os.getenv("SUPABASE_WORKSPACE_SLUG", "default").strip() or "default"


class EdgeFunctionTools(BaseTools):
    def _needs_handler_wrapper(self, runtime: str, source_code: str) -> bool:
        if runtime != "native-node20/v1":
            return False
        if "Deno.serve" in source_code:
            return False
        return bool(re.search(r"export\s+default\s+(async\s+)?function", source_code) or re.search(r"export\s+default\s*\(", source_code))

    def _build_deployment_payload(self, runtime: str, source_code: str, verify_jwt: bool, function_name: str) -> dict:
        entrypoint = self._get_entrypoint(runtime)
        files = [{
            "name": entrypoint,
            "content": source_code
        }]
        if self._needs_handler_wrapper(runtime, source_code):
            files = [
                {
                    "name": "handler.ts",
                    "content": source_code
                },
                {
                    "name": entrypoint,
                    "content": "import handler from './handler.ts'\nDeno.serve((req) => handler(req))\n"
                }
            ]
        return {
            "metadata": {
                "name": function_name,
                "slug": function_name,
                "entrypoint_path": entrypoint,
                "verify_jwt": verify_jwt
            },
            "files": files
        }

    def _normalize_function_payload(self, payload: object) -> object:
        if not isinstance(payload, dict):
            return payload
        result = dict(payload)
        files = result.get("files")
        entrypoint_path = result.get("entrypoint_path")
        if isinstance(files, list):
            source_code = None
            for file_info in files:
                if not isinstance(file_info, dict):
                    continue
                if entrypoint_path and file_info.get("name") == entrypoint_path and isinstance(file_info.get("content"), str):
                    source_code = file_info.get("content")
                    break
                if source_code is None and isinstance(file_info.get("content"), str):
                    source_code = file_info.get("content")
            if source_code is not None:
                result["source_code"] = source_code
        return result

    def _validate_function_name(self, function_name: str) -> None:
        return

    def _validate_runtime(self, runtime: str) -> None:
        """验证运行时"""
        if runtime not in RUNTIME_CONFIG:
            available = ", ".join(RUNTIME_CONFIG.keys())
            raise ValueError(f"Unsupported runtime '{runtime}'. Available: {available}")

    def _get_entrypoint(self, runtime: str) -> str:
        """获取运行时的入口文件"""
        return RUNTIME_CONFIG[runtime]["entrypoint"]

    def _validate_code_size(self, source_code: str) -> None:
        """验证代码大小"""
        code_size = len(source_code.encode('utf-8'))
        if code_size > MAX_CODE_SIZE:
            raise ValueError(f"Source code too large: {code_size} bytes (max {MAX_CODE_SIZE} bytes)")

    def _validate_runtime_compatibility(self, runtime: str, source_code: str) -> None:
        """验证运行时和代码的兼容性"""
        if runtime.startswith("native-python"):
            # 基本的 Python 语法检查
            if not any(keyword in source_code for keyword in ["def ", "import ", "from "]):
                logger.warning("Python code may be invalid - no function definitions or imports found")

    def _extract_error_text(self, payload: object) -> str:
        if isinstance(payload, dict):
            return json.dumps(payload, ensure_ascii=False)
        return str(payload)

    @handle_errors
    async def list_edge_functions(self, workspace_id: Optional[str] = None) -> List[EdgeFunction]:
        ws_id, branch_id = await self._resolve_target(workspace_id)
        logger.info(f"Listing edge functions for workspace {ws_id}")

        client = await self._get_client(ws_id, branch_id)
        result = await client.call_api(f"/v1/projects/{WORKSPACE_SLUG}/functions")

        functions = [EdgeFunction(**func) for func in result]
        logger.info(f"Found {len(functions)} edge functions")
        return functions
    
    @handle_errors
    async def get_edge_function(self, function_name: str, workspace_id: Optional[str] = None) -> dict:
        self._validate_function_name(function_name)
        ws_id, branch_id = await self._resolve_target(workspace_id)
        logger.info(f"Getting edge function '{function_name}' from workspace {ws_id}")

        client = await self._get_client(ws_id, branch_id)
        encoded_name = quote(function_name, safe="")
        try:
            result = await client.call_api(f"/v1/projects/{WORKSPACE_SLUG}/functions/{encoded_name}")
        except SupabaseApiError as e:
            payload_text = self._extract_error_text(e.payload).lower()
            if "function not found" in payload_text or "not found" in payload_text:
                raise ValueError(f"Edge function '{function_name}' not found")
            raise
        normalized_result = self._normalize_function_payload(result)
        if isinstance(normalized_result, dict):
            return normalized_result
        return EdgeFunction(**result).model_dump()
    
    @handle_errors
    @read_only_check
    async def deploy_edge_function(
        self,
        function_name: str,
        source_code: str,
        verify_jwt: bool = True,
        runtime: str = "native-node20/v1",
        import_map: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> dict:
        """
        部署边缘函数

        Args:
            function_name: 函数名称
            source_code: 源代码
            verify_jwt: 是否验证 JWT
            runtime: 运行时环境 (native-node20/v1, native-python3.9/v1, etc.)
            import_map: 可选的 import map JSON
            workspace_id: 工作空间 ID

        Returns:
            部署结果字典

        Raises:
            ValueError: 参数验证失败
        """
        # 验证输入
        self._validate_function_name(function_name)
        self._validate_runtime(runtime)

        if not source_code or not source_code.strip():
            raise ValueError("Source code cannot be empty")

        # HTML 反转义，防止代码中的特殊字符被转义
        source_code = html.unescape(source_code)

        self._validate_code_size(source_code)
        self._validate_runtime_compatibility(runtime, source_code)

        ws_id, branch_id = await self._resolve_target(workspace_id)
        entrypoint = self._get_entrypoint(runtime)

        logger.info(
            "Deploying edge function",
            extra={
                "function_name": function_name,
                "workspace_id": ws_id,
                "branch_id": branch_id,
                "runtime": runtime,
                "verify_jwt": verify_jwt,
                "entrypoint": entrypoint,
                "code_size": len(source_code)
            }
        )

        client = await self._get_client(ws_id, branch_id)

        encoded_name = quote(function_name, safe="")

        data = self._build_deployment_payload(runtime, source_code, verify_jwt, function_name)

        if import_map:
            try:
                import_map_data = json.loads(import_map)
                data["metadata"]["import_map_path"] = "import_map.json"
                data["files"].append({
                    "name": "import_map.json",
                    "content": json.dumps(import_map_data)
                })
                logger.debug("Added import map to deployment")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid import map JSON: {e}")

        # AIDAP 部署 API 路径
        result = await client.call_api(
            f"/v1/projects/{WORKSPACE_SLUG}/functions/deploy?slug={encoded_name}",
            method="POST",
            json_data=data
        )

        logger.info(
            f"Successfully deployed edge function '{function_name}'",
            extra={"function_id": result.get("id"), "version": result.get("version")}
        )

        if isinstance(result, dict) and not result.get("runtime"):
            result["runtime"] = runtime
        return result
    
    @handle_errors
    @read_only_check
    async def delete_edge_function(self, function_name: str, workspace_id: Optional[str] = None) -> dict:
        self._validate_function_name(function_name)
        ws_id, branch_id = await self._resolve_target(workspace_id)
        logger.info(f"Deleting edge function '{function_name}' from workspace {ws_id}")

        client = await self._get_client(ws_id, branch_id)
        encoded_name = quote(function_name, safe="")
        await client.call_api(f"/v1/projects/{WORKSPACE_SLUG}/functions/{encoded_name}", method="DELETE")

        logger.info(f"Successfully deleted edge function '{function_name}'")
        return {"success": True, "message": "Edge function deleted successfully"}
