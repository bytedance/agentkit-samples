# Copyright (c) 2026 ByteDance Ltd. and/or its affiliates
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

"""
SKILL内部异常类定义模块
"""


class SkillException(Exception):
    """SKILL基础异常类

    所有SKILL内部异常的基类，提供统一的异常处理接口
    """

    def __init__(self, code: str, message: str):
        """
        Args:
            code: 错误码，用于标识具体错误类型
            message: 错误描述信息
            detail: 错误详情，可选
        """
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self):
        return f"[{self.code}] {self.message}"

    def to_dict(self):
        """将异常转换为字典格式，便于序列化输出"""
        return {"code": self.code, "message": self.message}
