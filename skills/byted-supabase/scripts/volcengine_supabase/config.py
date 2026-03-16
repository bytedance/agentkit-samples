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
import os
import logging

logger = logging.getLogger(__name__)

READ_ONLY = os.getenv("READ_ONLY", "false").lower() == "true"

VOLCENGINE_ACCESS_KEY = os.getenv("VOLCENGINE_ACCESS_KEY")
VOLCENGINE_SECRET_KEY = os.getenv("VOLCENGINE_SECRET_KEY")
VOLCENGINE_SESSION_TOKEN = ""
VOLCENGINE_REGION = os.getenv("VOLCENGINE_REGION", "cn-beijing")

# 当环境变量未设置时，尝试从 vefaas IAM 获取凭证（沙箱环境）
if not (VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY):
    try:
        from veadk.auth.veauth.utils import get_credential_from_vefaas_iam
    except ImportError:
        get_credential_from_vefaas_iam = None

    if get_credential_from_vefaas_iam:
        try:
            cred = get_credential_from_vefaas_iam()
            VOLCENGINE_ACCESS_KEY = cred.access_key_id
            VOLCENGINE_SECRET_KEY = cred.secret_access_key
            VOLCENGINE_SESSION_TOKEN = cred.session_token
        except Exception as e:
            logger.warning(f"Failed to get credential from vefaas IAM: {e}")

# 验证必需的环境变量
if not VOLCENGINE_ACCESS_KEY:
    logger.warning("VOLCENGINE_ACCESS_KEY not set")
if not VOLCENGINE_SECRET_KEY:
    logger.warning("VOLCENGINE_SECRET_KEY not set")

_default_branch_cache = {}
_endpoint_cache = {}
_api_key_cache = {}
_branch_workspace_cache = {}


def get_branch_cache():
    return _default_branch_cache


def get_endpoint_cache():
    return _endpoint_cache


def get_api_key_cache():
    return _api_key_cache


def get_branch_workspace_cache():
    return _branch_workspace_cache


def clear_branch_cache(workspace_id: str = None):
    if workspace_id:
        _default_branch_cache.pop(workspace_id, None)
    else:
        _default_branch_cache.clear()


def clear_endpoint_cache(workspace_id: str = None, branch_id: str = None):
    if workspace_id and branch_id:
        _endpoint_cache.pop(f"{workspace_id}:{branch_id}", None)
    elif workspace_id:
        _endpoint_cache.pop(workspace_id, None)
        keys_to_delete = [key for key in _endpoint_cache if key.startswith(f"{workspace_id}:")]
        for key in keys_to_delete:
            _endpoint_cache.pop(key, None)
    else:
        _endpoint_cache.clear()


def clear_api_key_cache(workspace_id: str = None, branch_id: str = None):
    if workspace_id and branch_id:
        keys_to_delete = [key for key in _api_key_cache if key.startswith(f"{workspace_id}:") and key.endswith(f":{branch_id}")]
        for key in keys_to_delete:
            _api_key_cache.pop(key, None)
    elif workspace_id:
        keys_to_delete = [key for key in _api_key_cache if key == workspace_id or key.startswith(f"{workspace_id}:")]
        for key in keys_to_delete:
            _api_key_cache.pop(key, None)
    else:
        _api_key_cache.clear()


def clear_branch_workspace_cache(workspace_id: str = None, branch_id: str = None):
    if branch_id:
        _branch_workspace_cache.pop(branch_id, None)
    elif workspace_id:
        branch_ids = [key for key, value in _branch_workspace_cache.items() if value == workspace_id]
        for key in branch_ids:
            _branch_workspace_cache.pop(key, None)
    else:
        _branch_workspace_cache.clear()


def clear_all_caches(workspace_id: str = None, branch_id: str = None):
    clear_branch_cache(workspace_id)
    clear_endpoint_cache(workspace_id, branch_id)
    clear_api_key_cache(workspace_id, branch_id)
    clear_branch_workspace_cache(workspace_id, branch_id)
