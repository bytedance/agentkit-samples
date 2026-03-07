from typing import Optional


def select_target_id(target_id: Optional[str], default_target_id: Optional[str]) -> Optional[str]:
    return target_id or default_target_id


async def resolve_target(aidap_client, target_id: Optional[str], default_target_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    resolved_id = select_target_id(target_id, default_target_id)
    if not resolved_id:
        return None, None
    return await aidap_client.resolve_workspace_and_branch(resolved_id)
