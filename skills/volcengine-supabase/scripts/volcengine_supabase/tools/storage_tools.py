from typing import Optional, List
import logging
import json
from .base import BaseTools
from ..utils import handle_errors, read_only_check
from ..models import StorageConfig

logger = logging.getLogger(__name__)


class StorageTools(BaseTools):
    def _normalize_allowed_mime_types(self, allowed_mime_types: Optional[str | list[str]]) -> Optional[list[str]]:
        if allowed_mime_types is None:
            return None
        values: list[str]
        if isinstance(allowed_mime_types, list):
            values = allowed_mime_types
        elif isinstance(allowed_mime_types, str):
            text = allowed_mime_types.strip()
            if not text:
                return None
            if text.startswith("["):
                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError("allowed_mime_types JSON value must be a list of strings")
                values = parsed
            else:
                values = text.split(",")
        else:
            raise ValueError("allowed_mime_types must be a string, JSON array string, or list of strings")
        result = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        if not result:
            return None
        return result

    @handle_errors
    async def list_storage_buckets(self, workspace_id: Optional[str] = None) -> List[dict]:
        ws_id, branch_id = await self._resolve_target(workspace_id)
        logger.info(f"Listing storage buckets for workspace {ws_id}")

        client = await self._get_client(ws_id, branch_id)
        result = await client.call_api("/storage/v1/bucket")

        logger.info(f"Found {len(result)} storage buckets")
        return result
    
    @handle_errors
    @read_only_check
    async def create_storage_bucket(
        self,
        bucket_name: str,
        public: bool = False,
        file_size_limit: Optional[int] = None,
        allowed_mime_types: Optional[str | list[str]] = None,
        workspace_id: Optional[str] = None
    ) -> dict:
        if not bucket_name or not bucket_name.strip():
            raise ValueError("Bucket name cannot be empty")

        ws_id, branch_id = await self._resolve_target(workspace_id)
        logger.info(
            f"Creating storage bucket '{bucket_name}'",
            extra={"workspace_id": ws_id, "branch_id": branch_id, "public": public}
        )

        client = await self._get_client(ws_id, branch_id)

        data = {
            "name": bucket_name,
            "public": public
        }
        if file_size_limit:
            data["file_size_limit"] = file_size_limit
        normalized_mime_types = self._normalize_allowed_mime_types(allowed_mime_types)
        if normalized_mime_types:
            data["allowed_mime_types"] = normalized_mime_types
        
        return await client.call_api("/storage/v1/bucket", method="POST", json_data=data)
    
    @handle_errors
    @read_only_check
    async def delete_storage_bucket(self, bucket_name: str, workspace_id: Optional[str] = None) -> dict:
        if not bucket_name or not bucket_name.strip():
            raise ValueError("Bucket name cannot be empty")
        ws_id, branch_id = await self._resolve_target(workspace_id)
        client = await self._get_client(ws_id, branch_id)
        response = await client.call_api(f"/storage/v1/bucket/{bucket_name}", method="DELETE")
        if isinstance(response, dict) and "error" in response:
            raise ValueError(response["error"])
        return {"success": True, "message": "Bucket deleted successfully"}
    
    @handle_errors
    async def get_storage_config(self, workspace_id: Optional[str] = None) -> StorageConfig:
        ws_id, branch_id = await self._resolve_target(workspace_id)
        client = await self._get_client(ws_id, branch_id)
        result = await client.call_api("/storage/v1/config")
        return StorageConfig(**result)
