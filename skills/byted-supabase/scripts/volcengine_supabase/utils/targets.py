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
from typing import Optional


def select_target_id(target_id: Optional[str], default_target_id: Optional[str]) -> Optional[str]:
    return target_id or default_target_id


async def resolve_target(aidap_client, target_id: Optional[str], default_target_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    resolved_id = select_target_id(target_id, default_target_id)
    if not resolved_id:
        return None, None
    return await aidap_client.resolve_workspace_and_branch(resolved_id)
