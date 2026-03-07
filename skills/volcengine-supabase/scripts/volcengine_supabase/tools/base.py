from typing import Optional
from ..platform import AidapClient, SupabaseClient
from ..utils import resolve_target, select_target_id


class BaseTools:
    """Base class for all tool classes"""

    def __init__(self, aidap_client: AidapClient, workspace_id: Optional[str] = None):
        self.aidap = aidap_client
        self.default_workspace_id = workspace_id

    def _get_workspace_id(self, workspace_id: Optional[str]) -> str:
        """Get workspace ID from parameter or default"""
        result = select_target_id(workspace_id, self.default_workspace_id)
        if not result:
            raise ValueError(
                "workspace_id is required: not provided as parameter and no default workspace_id configured. "
                "Please provide workspace_id or set DEFAULT_WORKSPACE_ID environment variable."
            )
        return result

    async def _resolve_target(self, workspace_id: Optional[str]) -> tuple[str, Optional[str]]:
        target = self._get_workspace_id(workspace_id)
        resolved_workspace_id, branch_id = await resolve_target(self.aidap, target, None)
        if not resolved_workspace_id:
            raise ValueError(
                "workspace_id is required: not provided as parameter and no default workspace_id configured. "
                "Please provide workspace_id or set DEFAULT_WORKSPACE_ID environment variable."
            )
        return resolved_workspace_id, branch_id

    async def _get_client(self, workspace_id: str, branch_id: Optional[str] = None) -> SupabaseClient:
        """Get Supabase client for workspace"""
        import logging
        logger = logging.getLogger(__name__)

        endpoint = await self.aidap.get_endpoint(workspace_id, branch_id=branch_id)
        logger.info(f"[DEBUG] Got endpoint for {workspace_id} branch={branch_id}: {endpoint}")
        if not endpoint:
            target = branch_id or workspace_id
            raise ValueError(f"Could not get endpoint for target {target}")

        api_key = await self.aidap.get_api_key(workspace_id, "service_role", branch_id=branch_id)
        logger.info(f"[DEBUG] Got API key for {workspace_id} branch={branch_id}: {'yes' if api_key else 'no'}")
        if not api_key:
            target = branch_id or workspace_id
            raise ValueError(f"Could not get API key for target {target}")

        return SupabaseClient(endpoint, api_key)
