import asyncio
import inspect
import logging
from typing import Any, Optional

from ..utils import compact_dict, pick_value, read_only_check, resolve_target, to_json

logger = logging.getLogger(__name__)


class WorkspaceTools:
    def __init__(self, aidap_client, default_workspace_id: Optional[str] = None):
        self.aidap_client = aidap_client
        self.default_workspace_id = default_workspace_id

    def _to_json(self, payload: dict) -> str:
        return to_json(payload)

    def _compact(self, payload: dict) -> dict:
        return compact_dict(payload)

    def _pick(self, source: Any, *field_names: str) -> Any:
        return pick_value(source, *field_names)

    async def _resolve_target(self, target_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        return await resolve_target(self.aidap_client, target_id, self.default_workspace_id)

    def _workspace_view(self, source: Any) -> dict:
        payload = {
            "workspace_id": self._pick(source, "workspace_id"),
            "workspace_name": self._pick(source, "workspace_name"),
            "status": self._pick(source, "workspace_status", "status"),
            "region": self._pick(source, "region_id", "region"),
            "created_at": self._pick(source, "create_time", "created_at"),
            "updated_at": self._pick(source, "update_time", "updated_at"),
            "engine_type": self._pick(source, "engine_type"),
            "engine_version": self._pick(source, "engine_version"),
            "deletion_protection_status": self._pick(source, "deletion_protection_status"),
        }
        return self._compact(payload)

    def _branch_view(self, branch: dict, workspace_payload: Optional[dict] = None) -> dict:
        workspace_payload = workspace_payload or {}
        payload = {
            "branch_id": branch.get("branch_id"),
            "branch_name": branch.get("branch_name") or branch.get("name"),
            "status": branch.get("status") or workspace_payload.get("status"),
            "default": branch.get("default"),
            "parent_id": branch.get("parent_id"),
            "workspace_id": workspace_payload.get("workspace_id") or branch.get("workspace_id"),
            "workspace_name": workspace_payload.get("workspace_name"),
            "created_at": branch.get("created_at") or workspace_payload.get("created_at"),
            "updated_at": branch.get("updated_at") or workspace_payload.get("updated_at"),
            "engine_type": workspace_payload.get("engine_type"),
            "engine_version": workspace_payload.get("engine_version"),
            "deletion_protection_status": workspace_payload.get("deletion_protection_status"),
            "target_type": "branch",
        }
        return self._compact(payload)

    def _describe_workspaces_response(self):
        from volcenginesdkaidap.models import DescribeWorkspacesRequest, FilterForDescribeWorkspacesInput

        parameters = inspect.signature(FilterForDescribeWorkspacesInput).parameters
        filter_kwargs = {
            "name": "DBEngineVersion",
            "value": "Supabase_1_24",
        }
        if "mode" in parameters:
            filter_kwargs["mode"] = "Exact"
        filters = [FilterForDescribeWorkspacesInput(**filter_kwargs)]
        request = DescribeWorkspacesRequest(filters=filters)
        return self.aidap_client.client.describe_workspaces(request)

    def _find_workspace_source(self, workspace_id: str) -> Optional[Any]:
        response = self._describe_workspaces_response()
        for workspace in list(getattr(response, "workspaces", []) or []):
            if self._pick(workspace, "workspace_id") == workspace_id:
                return workspace
        return None

    def _error_detail(self, code: str, message: str, retriable: bool = False) -> dict:
        return {
            "code": code,
            "message": message,
            "retriable": retriable,
        }

    def _mask_key(self, value: Optional[str], reveal: bool) -> Optional[str]:
        if value is None:
            return None
        if reveal:
            return value
        if len(value) <= 12:
            return "*" * len(value)
        return f"{value[:6]}...{value[-4:]}"

    async def list_workspaces(self) -> str:
        try:
            response = self._describe_workspaces_response()
            raw_workspaces = list(getattr(response, "workspaces", []) or [])
            workspaces = [self._workspace_view(workspace) for workspace in raw_workspaces]
            return self._to_json({
                "success": True,
                "workspaces": workspaces,
                "count": len(workspaces),
            })
        except Exception as e:
            logger.error(f"Error listing workspaces: {e}")
            return self._to_json({
                "success": False,
                "error": str(e),
            })

    async def get_workspace(self, workspace_id: str) -> str:
        try:
            ws_id, branch_id = await self._resolve_target(workspace_id)
            if not ws_id:
                return self._to_json({
                    "success": False,
                    "error": "workspace_id is required",
                })
            workspace_source = self._find_workspace_source(ws_id)
            if workspace_source is None:
                return self._to_json({
                    "success": False,
                    "error": "Workspace not found",
                })
            workspace_info = self._workspace_view(workspace_source)
            if branch_id:
                branch = await self.aidap_client.get_branch(ws_id, branch_id)
                if branch:
                    workspace_info.update(self._branch_view(branch, workspace_info))
            return self._to_json({
                "success": True,
                "workspace": workspace_info,
            })
        except Exception as e:
            logger.error(f"Error getting workspace: {e}")
            return self._to_json({
                "success": False,
                "error": str(e),
            })

    @read_only_check
    async def create_workspace(
        self,
        workspace_name: str,
        engine_version: str = "Supabase_1_24",
        engine_type: str = "Supabase",
    ) -> str:
        if not workspace_name or not workspace_name.strip():
            return self._to_json({"success": False, "error": "workspace_name is required"})
        result = await self.aidap_client.create_workspace(
            workspace_name=workspace_name.strip(),
            engine_type=engine_type,
            engine_version=engine_version,
        )
        if not isinstance(result, dict):
            return self._to_json({"success": False, "error": "Unexpected create workspace response"})
        if result.get("success"):
            mapped = {
                "success": True,
                "workspace_id": result.get("workspace_id"),
                "workspace_name": result.get("workspace_name") or workspace_name.strip(),
                "engine_type": result.get("engine_type"),
                "engine_version": result.get("engine_version"),
            }
            return self._to_json(self._compact(mapped))
        return self._to_json(result)

    @read_only_check
    async def restore_workspace(self, workspace_id: Optional[str] = None) -> str:
        ws_id, _ = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({"success": False, "error": "workspace_id is required"})
        result = await self.aidap_client.start_workspace(ws_id)
        return self._to_json(result if isinstance(result, dict) else {"success": bool(result), "workspace_id": ws_id})

    @read_only_check
    async def pause_workspace(self, workspace_id: Optional[str] = None) -> str:
        ws_id, _ = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({"success": False, "error": "workspace_id is required"})
        result = await self.aidap_client.stop_workspace(ws_id)
        return self._to_json(result if isinstance(result, dict) else {"success": bool(result), "workspace_id": ws_id})

    @read_only_check
    async def create_branch(
        self,
        name: str = "develop",
        workspace_id: Optional[str] = None,
    ) -> str:
        ws_id, _ = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({"success": False, "error": "workspace_id is required"})

        result = await self.aidap_client.create_branch(ws_id, name)
        if result.get("success") and result.get("branch_id"):
            branch_payload = self._branch_view(result, {"workspace_id": ws_id})
            branch_payload["branch_name"] = branch_payload.get("branch_name") or name
            response_payload = {
                "success": True,
                **branch_payload,
            }
            endpoint = await self.aidap_client.get_endpoint(ws_id, branch_id=result["branch_id"], use_cache=False)
            if endpoint:
                response_payload["workspace_url"] = endpoint
                response_payload["api_url"] = endpoint
            return self._to_json(self._compact(response_payload))
        return self._to_json(result)

    async def list_branches(self, workspace_id: Optional[str] = None) -> str:
        ws_id, _ = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({"success": False, "error": "workspace_id is required"})
        try:
            workspace_source = self._find_workspace_source(ws_id)
            workspace_payload = self._workspace_view(workspace_source) if workspace_source is not None else {"workspace_id": ws_id}
            branches = await self.aidap_client.list_branches(ws_id)
            normalized_branches = [self._branch_view(branch, workspace_payload) for branch in branches]
            return self._to_json({"success": True, "branches": normalized_branches})
        except Exception as e:
            logger.error(f"Error listing branches: {e}")
            return self._to_json({"success": False, "error": str(e)})

    @read_only_check
    async def delete_branch(self, branch_id: str, workspace_id: Optional[str] = None) -> str:
        ws_id, _ = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({
                "success": False,
                "error": "workspace_id is required",
                "error_detail": self._error_detail("MissingWorkspaceId", "workspace_id is required", False),
            })
        if not branch_id or not branch_id.strip():
            return self._to_json({
                "success": False,
                "error": "branch_id is required",
                "error_detail": self._error_detail("MissingBranchId", "branch_id is required", False),
            })
        normalized_branch_id = branch_id.strip()

        try:
            branches = await self.aidap_client.list_branches(ws_id)
            exists = any(branch.get("branch_id") == normalized_branch_id for branch in branches)
            if not exists:
                return self._to_json({
                    "success": False,
                    "error": f"Branch '{normalized_branch_id}' not found in workspace '{ws_id}'",
                    "error_detail": self._error_detail(
                        "BranchNotFound",
                        f"Branch '{normalized_branch_id}' not found in workspace '{ws_id}'",
                        False,
                    ),
                })
        except Exception as e:
            logger.error(f"Error checking branch before delete: {e}")
            return self._to_json({
                "success": False,
                "error": str(e),
                "error_detail": self._error_detail("ListBranchesFailed", str(e), True),
            })

        result = await self.aidap_client.delete_branch(ws_id, normalized_branch_id)
        if not result.get("success"):
            error_text = result.get("error", "delete branch failed")
            return self._to_json({
                "success": False,
                "error": error_text,
                "error_detail": self._error_detail(
                    result.get("code", "DeleteBranchFailed"),
                    error_text,
                    bool(result.get("retriable", False)),
                ),
            })

        max_confirm_attempts = 20
        last_list_error: Optional[str] = None
        for _ in range(max_confirm_attempts):
            await asyncio.sleep(1)
            try:
                branches = await self.aidap_client.list_branches(ws_id)
                exists = any(branch.get("branch_id") == normalized_branch_id for branch in branches)
                if not exists:
                    return self._to_json({"success": True, "branch_id": normalized_branch_id, "workspace_id": ws_id})
            except Exception as e:
                last_list_error = str(e)

        if last_list_error:
            return self._to_json({
                "success": False,
                "error": f"Delete requested for branch '{normalized_branch_id}' but verification failed: {last_list_error}",
                "error_detail": self._error_detail(
                    "DeleteBranchVerifyFailed",
                    f"Delete requested for branch '{normalized_branch_id}' but verification failed: {last_list_error}",
                    True,
                ),
            })
        return self._to_json({
            "success": False,
            "error": f"Delete requested for branch '{normalized_branch_id}' but branch still exists",
            "error_detail": self._error_detail(
                "BranchStillExists",
                f"Delete requested for branch '{normalized_branch_id}' but branch still exists",
                True,
            ),
        })

    async def get_workspace_url(self, workspace_id: Optional[str] = None) -> str:
        ws_id, branch_id = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({"success": False, "error": "workspace_id is required"})

        endpoint = await self.aidap_client.get_endpoint(ws_id, branch_id=branch_id)
        if not endpoint:
            target_id = branch_id or ws_id
            return self._to_json({
                "success": False,
                "error": f"Could not get endpoint for workspace {target_id}",
            })

        payload = {
            "success": True,
            "workspace_id": ws_id,
            "workspace_url": endpoint,
            "api_url": endpoint,
        }
        if branch_id:
            payload["branch_id"] = branch_id
            payload["target_type"] = "branch"
        return self._to_json(payload)

    async def _get_api_keys_payload(self, workspace_id: str, branch_id: Optional[str] = None, reveal: bool = False) -> dict:
        resolved_branch_id = branch_id or await self.aidap_client.get_default_branch_id(workspace_id)
        if not resolved_branch_id:
            raise RuntimeError(f"Could not resolve default branch for workspace {workspace_id}")
        keys = await self.aidap_client.get_api_keys(workspace_id, branch_id=resolved_branch_id)
        publishable_key = None
        anon_key = None
        service_role_key = None
        masked_keys = []
        for key in keys:
            key_type = (key.get("type") or "").lower()
            value = key.get("key")
            if key_type == "public":
                publishable_key = value
                anon_key = value
            if key_type == "service":
                service_role_key = value
            masked_keys.append({
                **key,
                "key": self._mask_key(value, reveal),
            })
        payload = {
            "success": True,
            "workspace_id": workspace_id,
            "reveal": reveal,
            "publishable_key": self._mask_key(publishable_key, reveal),
            "anon_key": self._mask_key(anon_key, reveal),
            "service_role_key": self._mask_key(service_role_key, reveal),
            "keys": masked_keys,
        }
        if resolved_branch_id:
            payload["branch_id"] = resolved_branch_id
            payload["target_type"] = "branch"
        return payload

    async def get_publishable_keys(self, workspace_id: Optional[str] = None, reveal: bool = False) -> str:
        ws_id, branch_id = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({"success": False, "error": "workspace_id is required"})

        try:
            payload = await self._get_api_keys_payload(ws_id, branch_id=branch_id, reveal=reveal)
            return self._to_json(payload)
        except Exception as e:
            logger.error(f"Error getting publishable keys: {e}")
            return self._to_json({"success": False, "error": str(e)})

    @read_only_check
    async def reset_branch(
        self,
        branch_id: str,
        migration_version: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> str:
        ws_id, _ = await self._resolve_target(workspace_id)
        if not ws_id:
            return self._to_json({
                "success": False,
                "error": "workspace_id is required",
            })

        try:
            result = await self.aidap_client.reset_branch(ws_id, branch_id)
            if not isinstance(result, dict):
                result = {"success": bool(result)}
            if result.get("success"):
                result.setdefault("workspace_id", ws_id)
                result.setdefault("branch_id", branch_id)
            if migration_version:
                result["warning"] = "migration_version is ignored because current AIDAP reset_branch API does not support version-targeted reset"
            return self._to_json(result)
        except Exception as e:
            logger.error(f"Error resetting branch: {e}")
            return self._to_json({
                "success": False,
                "error": str(e),
            })
