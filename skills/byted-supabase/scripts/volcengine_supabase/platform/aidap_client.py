# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import asyncio
import os
import random
from typing import Any, Optional
from ..config import (
    VOLCENGINE_ACCESS_KEY,
    VOLCENGINE_SECRET_KEY,
    VOLCENGINE_SESSION_TOKEN,
    VOLCENGINE_REGION,
    get_branch_cache,
    get_branch_workspace_cache,
    get_endpoint_cache,
    get_api_key_cache,
    clear_all_caches,
)
from ..utils import pick_value

logger = logging.getLogger(__name__)
ENDPOINT_SCHEME = os.getenv("SUPABASE_ENDPOINT_SCHEME", "http").strip().lower() or "http"

try:
    import volcenginesdkcore
    from volcenginesdkaidap import AIDAPApi
    from volcenginesdkaidap.models import (
        DescribeBranchesRequest,
        DescribeWorkspacesRequest,
        DescribeWorkspaceEndpointRequest,
        DescribeAPIKeysRequest,
        ResetBranchRequest,
        CreateBranchRequest,
        DeleteBranchRequest,
        BranchSettingsForCreateBranchInput,
        CreateWorkspaceRequest,
        WorkspaceSettingsForCreateWorkspaceInput,
        BranchSettingsForCreateWorkspaceInput,
        ComputeSettingsForCreateWorkspaceInput,
        StartWorkspaceRequest,
        StopWorkspaceRequest,
    )
except ImportError:
    logger.error("volcengine-python-sdk not installed")
    raise


class AidapClient:
    def __init__(self) -> None:
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = VOLCENGINE_ACCESS_KEY
        configuration.sk = VOLCENGINE_SECRET_KEY
        configuration.region = VOLCENGINE_REGION
        if VOLCENGINE_SESSION_TOKEN:
            configuration.session_token = VOLCENGINE_SESSION_TOKEN

        api_client = volcenginesdkcore.ApiClient(configuration)
        self.client = AIDAPApi(api_client)

    def _branch_error_code(self, error_text: str) -> str:
        if "OperationDenied_BranchNotReady" in error_text:
            return "OperationDenied_BranchNotReady"
        if "BranchStatusNotMatch" in error_text:
            return "BranchStatusNotMatch"
        if "BranchNotFound" in error_text:
            return "BranchNotFound"
        return "AIDAPError"

    def _pick_value(self, source: Any, *field_names: str) -> Any:
        return pick_value(source, *field_names)

    def _looks_like_branch_id(self, value: Optional[str]) -> bool:
        return bool(value and value.strip().startswith("br-"))

    def _cache_branch_workspace(self, workspace_id: Optional[str], branch_id: Optional[str]) -> None:
        if workspace_id and branch_id:
            get_branch_workspace_cache()[branch_id] = workspace_id

    def _workspace_ids_from_response(self, response: Any) -> list[str]:
        workspace_ids = []
        for workspace in list(getattr(response, "workspaces", []) or []):
            workspace_id = self._pick_value(workspace, "workspace_id")
            if workspace_id:
                workspace_ids.append(workspace_id)
        return workspace_ids

    def _branch_payload(self, branch: Any, fallback_name: Optional[str] = None) -> dict:
        parent_branch = self._pick_value(branch, "parent_branch")
        parent_id = self._pick_value(parent_branch, "branch_id", "parent_id")
        payload = {
            "branch_id": self._pick_value(branch, "branch_id"),
            "name": self._pick_value(branch, "name", "branch_name") or fallback_name,
            "status": self._pick_value(branch, "status", "branch_status"),
            "default": bool(self._pick_value(branch, "default", "is_default") or False),
            "parent_id": parent_id or self._pick_value(branch, "parent_id", "parent_branch_id"),
            "workspace_id": self._pick_value(branch, "workspace_id"),
            "archived": self._pick_value(branch, "archived"),
            "protected": self._pick_value(branch, "protected"),
            "created_at": self._pick_value(branch, "create_time", "created_at"),
            "updated_at": self._pick_value(branch, "update_time", "updated_at"),
        }
        result = {key: value for key, value in payload.items() if value is not None}
        self._cache_branch_workspace(result.get("workspace_id"), result.get("branch_id"))
        return result

    def _describe_supabase_workspaces_response(self):
        request = DescribeWorkspacesRequest()
        return self.client.describe_workspaces(request)

    async def _find_branch(
        self,
        workspace_id: str,
        branch_id: Optional[str] = None,
        name: Optional[str] = None,
        max_attempts: int = 6,
        ) -> Optional[dict]:
        for attempt in range(1, max_attempts + 1):
            branches = await self.list_branches(workspace_id)
            for branch in branches:
                if branch_id and branch.get("branch_id") == branch_id:
                    return branch
                if name and branch.get("name") == name:
                    return branch
            if attempt < max_attempts:
                await self._sleep_backoff(attempt, base_seconds=0.5, max_seconds=3.0)
        return None

    async def _find_workspace_id_for_branch(self, branch_id: str) -> Optional[str]:
        cached_workspace_id = get_branch_workspace_cache().get(branch_id)
        if cached_workspace_id:
            return cached_workspace_id
        response = self._describe_supabase_workspaces_response()
        for workspace_id in self._workspace_ids_from_response(response):
            branch = await self._find_branch(workspace_id, branch_id=branch_id, max_attempts=1)
            if branch:
                self._cache_branch_workspace(workspace_id, branch_id)
                return workspace_id
        return None

    async def resolve_workspace_and_branch(self, workspace_or_branch_id: str) -> tuple[str, Optional[str]]:
        normalized_id = workspace_or_branch_id.strip()
        if not self._looks_like_branch_id(normalized_id):
            return normalized_id, None
        workspace_id = await self._find_workspace_id_for_branch(normalized_id)
        if not workspace_id:
            raise ValueError(f"Could not resolve workspace for branch {normalized_id}")
        return workspace_id, normalized_id

    async def get_branch(self, workspace_id: str, branch_id: str) -> Optional[dict]:
        return await self._find_branch(workspace_id, branch_id=branch_id, max_attempts=1)

    async def _sleep_backoff(
        self,
        attempt: int,
        base_seconds: float = 1.0,
        max_seconds: float = 10.0,
    ) -> None:
        delay = min(max_seconds, base_seconds * (2 ** max(attempt - 1, 0)))
        jitter = random.uniform(0.0, delay * 0.2)
        await asyncio.sleep(delay + jitter)
    
    async def get_default_branch_id(self, workspace_id: str, use_cache: bool = True) -> Optional[str]:
        cache = get_branch_cache()
        if use_cache and workspace_id in cache:
            return cache[workspace_id]
        
        try:
            request = DescribeBranchesRequest(workspace_id=workspace_id)
            response = self.client.describe_branches(request)
            
            if hasattr(response, 'branches') and response.branches:
                for branch in response.branches:
                    if getattr(branch, 'default', False):
                        branch_id = branch.branch_id
                        cache[workspace_id] = branch_id
                        self._cache_branch_workspace(workspace_id, branch_id)
                        return branch_id
                
                first_branch = response.branches[0]
                branch_id = first_branch.branch_id
                cache[workspace_id] = branch_id
                self._cache_branch_workspace(workspace_id, branch_id)
                return branch_id
            
            return None
        except Exception as e:
            logger.error(f"Error getting default branch: {e}")
            return None
    
    async def list_branches(self, workspace_id: str) -> list[dict]:
        try:
            request = DescribeBranchesRequest(workspace_id=workspace_id)
            response = self.client.describe_branches(request)

            branches = []
            if hasattr(response, 'branches') and response.branches:
                for branch in response.branches:
                    branches.append(self._branch_payload(branch))
            return branches
        except Exception as e:
            logger.error(f"Error listing branches: {e}")
            raise RuntimeError(str(e))

    async def create_branch(self, workspace_id: str, name: str = "develop") -> dict:
        try:
            request = CreateBranchRequest(
                workspace_id=workspace_id,
                branch_settings=BranchSettingsForCreateBranchInput(name=name),
            )
            response = self.client.create_branch(request)

            branch_id = getattr(response, 'branch_id', None)
            if not branch_id and hasattr(response, 'branch'):
                branch_id = getattr(response.branch, 'branch_id', None)

            branch_payload = None
            if branch_id or name:
                try:
                    branch_payload = await self._find_branch(workspace_id, branch_id, name)
                except Exception as lookup_error:
                    logger.warning(f"Error loading created branch details: {lookup_error}")

            result = {
                "success": True,
                "branch_id": branch_id,
                "workspace_id": workspace_id,
                "name": name,
            }
            if branch_payload:
                result.update(branch_payload)
            return result
        except Exception as e:
            logger.error(f"Error creating branch: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def create_workspace(
        self,
        workspace_name: str,
        engine_type: str = "Supabase",
        engine_version: str = "Supabase_1_24",
    ) -> dict:
        try:
            request = CreateWorkspaceRequest(
                workspace_name=workspace_name,
                engine_type=engine_type,
                engine_version=engine_version,
                branch_settings=BranchSettingsForCreateWorkspaceInput(branch_name="main"),
                compute_settings=ComputeSettingsForCreateWorkspaceInput(
                    auto_scaling_limit_min_cu=0.25,
                    auto_scaling_limit_max_cu=1,
                    suspend_timeout_seconds=300
                ),
                workspace_settings=WorkspaceSettingsForCreateWorkspaceInput(
                    public_connection="Disabled",
                    deletion_protection="Disabled"
                ),
            )
            response = self.client.create_workspace(request)

            workspace_id = getattr(response, 'workspace_id', None)
            if not workspace_id and hasattr(response, 'workspace'):
                workspace_id = getattr(response.workspace, 'workspace_id', None)

            return {
                "success": True,
                "workspace_id": workspace_id,
                "workspace_name": workspace_name,
                "engine_type": engine_type,
                "engine_version": engine_version,
            }
        except Exception as e:
            logger.error(f"Error creating workspace: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def start_workspace(self, workspace_id: str) -> dict:
        try:
            request = StartWorkspaceRequest(workspace_id=workspace_id)
            self.client.start_workspace(request)
            return {"success": True, "workspace_id": workspace_id, "status": "starting"}
        except Exception as e:
            logger.error(f"Error starting workspace: {e}")
            return {"success": False, "error": str(e)}

    async def stop_workspace(self, workspace_id: str) -> dict:
        try:
            request = StopWorkspaceRequest(workspace_id=workspace_id)
            self.client.stop_workspace(request)
            return {"success": True, "workspace_id": workspace_id, "status": "stopping"}
        except Exception as e:
            logger.error(f"Error stopping workspace: {e}")
            return {"success": False, "error": str(e)}

    async def delete_branch(self, workspace_id: str, branch_id: str) -> dict:
        max_attempts = 8
        for attempt in range(1, max_attempts + 1):
            try:
                request = DeleteBranchRequest(
                    workspace_id=workspace_id,
                    branch_id=branch_id,
                )
                self.client.delete_branch(request)
                clear_all_caches(workspace_id, branch_id)
                return {"success": True}
            except Exception as e:
                error_text = str(e)
                code = self._branch_error_code(error_text)
                retriable = code in {"OperationDenied_BranchNotReady", "BranchStatusNotMatch"}
                if retriable and attempt < max_attempts:
                    await self._sleep_backoff(attempt)
                    continue
                logger.error(f"Error deleting branch: {e}")
                return {
                    "success": False,
                    "error": error_text,
                    "code": code,
                    "retriable": retriable,
                }
        return {
            "success": False,
            "error": "delete_branch failed after retries",
            "code": "OperationDenied_BranchNotReady",
            "retriable": True,
        }

    async def get_endpoint(self, workspace_id: str, branch_id: Optional[str] = None, use_cache: bool = True) -> Optional[str]:
        # 检查缓存
        cache_key = f"{workspace_id}:{branch_id}" if branch_id else workspace_id
        endpoint_cache = get_endpoint_cache()

        if use_cache and cache_key in endpoint_cache:
            return endpoint_cache[cache_key]

        if not branch_id:
            branch_id = await self.get_default_branch_id(workspace_id)
            if not branch_id:
                return None

        try:
            request = DescribeWorkspaceEndpointRequest(
                workspace_id=workspace_id,
                branch_id=branch_id
            )
            response = self.client.describe_workspace_endpoint(request)

            if hasattr(response, 'endpoints') and response.endpoints:
                domains = []
                for endpoint in response.endpoints:
                    if hasattr(endpoint, 'addresses') and endpoint.addresses:
                        for addr in endpoint.addresses:
                            if hasattr(addr, 'address_domain'):
                                domains.append(addr.address_domain)

                for domain in domains:
                    if 'volces.com' in domain and 'ivolces.com' not in domain:
                        if ENDPOINT_SCHEME == "https":
                            result = f"https://{domain}"
                        else:
                            result = f"http://{domain}:80"
                        endpoint_cache[cache_key] = result
                        return result

                if domains:
                    if ENDPOINT_SCHEME == "https":
                        result = f"https://{domains[0]}"
                    else:
                        result = f"http://{domains[0]}:80"
                    endpoint_cache[cache_key] = result
                    return result

            return None
        except Exception as e:
            logger.error(f"Error getting endpoint: {e}")
            return None
    
    async def reset_branch(self, workspace_id: str, branch_id: str) -> dict:
        max_attempts = 8
        for attempt in range(1, max_attempts + 1):
            try:
                request = ResetBranchRequest(
                    workspace_id=workspace_id,
                    branch_id=branch_id,
                )
                self.client.reset_branch(request)
                return {"success": True}
            except Exception as e:
                error_text = str(e)
                code = self._branch_error_code(error_text)
                retriable = code in {"OperationDenied_BranchNotReady", "BranchStatusNotMatch"}
                if retriable and attempt < max_attempts:
                    await self._sleep_backoff(attempt)
                    continue
                logger.error(f"Error resetting branch: {e}")
                return {
                    "success": False,
                    "error": error_text,
                    "code": code,
                    "retriable": retriable,
                }
        return {
            "success": False,
            "error": "reset_branch failed after retries",
            "code": "OperationDenied_BranchNotReady",
            "retriable": True,
        }

    async def get_api_key(self, workspace_id: str, key_type: str = "service_role",
                         branch_id: Optional[str] = None, use_cache: bool = True) -> Optional[str]:
        # 检查缓存
        cache_key = f"{workspace_id}:{key_type}:{branch_id}" if branch_id else f"{workspace_id}:{key_type}"
        api_key_cache = get_api_key_cache()

        if use_cache and cache_key in api_key_cache:
            return api_key_cache[cache_key]

        if not branch_id:
            branch_id = await self.get_default_branch_id(workspace_id)
            if not branch_id:
                return None

        try:
            request = DescribeAPIKeysRequest(
                workspace_id=workspace_id,
                branch_id=branch_id
            )
            response = self.client.describe_api_keys(request)

            if hasattr(response, 'api_keys') and response.api_keys:
                type_mapping = {
                    "service_role": "Service",
                    "anon": "Public"
                }
                target_type = type_mapping.get(key_type, "Service")

                for key in response.api_keys:
                    if hasattr(key, 'type') and key.type == target_type:
                        result = key.key if hasattr(key, 'key') else None
                        if result:
                            api_key_cache[cache_key] = result
                        return result

            return None
        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None

    async def get_api_keys(
        self,
        workspace_id: str,
        branch_id: Optional[str] = None,
        use_default_branch: bool = False,
    ) -> list[dict]:
        if use_default_branch and not branch_id:
            branch_id = await self.get_default_branch_id(workspace_id)
            if not branch_id:
                raise RuntimeError(f"Could not get default branch for workspace {workspace_id}")

        request_kwargs = {"workspace_id": workspace_id}
        if branch_id:
            request_kwargs["branch_id"] = branch_id

        request = DescribeAPIKeysRequest(**request_kwargs)
        response = self.client.describe_api_keys(request)

        keys = []
        if hasattr(response, 'api_keys') and response.api_keys:
            for key in response.api_keys:
                keys.append({
                    "type": getattr(key, "type", None),
                    "key": getattr(key, "key", None),
                    "description": getattr(key, "description", None),
                })
        return keys
