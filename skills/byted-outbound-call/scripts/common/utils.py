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

def is_exec_context():
    return os.getenv("OPENCLAW_SHELL") == "exec"

def print_openclaw_session_env(logger):
    logger.info(f"通道：%s", os.getenv("OPENCLAW_CHANNEL", "unknown"))
    logger.info(f"用户ID：%s", os.getenv("OPENCLAW_USER_ID", "unknown"))
    logger.info(f"会话ID：%s", os.getenv("OPENCLAW_SESSION_ID", "unknown"))
    logger.info(f"环境变量：{os.environ}")

    logger.info(f"trigger_type：%s", os.environ.get("OPENCLAW_TRIGGER_TYPE", "unknown"))
    logger.info(f"是否为exec执行场景: {is_exec_context()}")