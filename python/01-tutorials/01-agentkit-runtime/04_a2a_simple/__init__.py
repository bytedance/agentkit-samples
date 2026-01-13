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

# 注意：此模块不适合在 veadk web 中自动加载
# a2a_simple 需要先启动远程服务，然后才能运行客户端
# 请参考 README.md 中的运行方式说明

# 不导入 root_agent，避免在模块加载时初始化 RemoteVeAgent
# from .agent import root_agent  # noqa
