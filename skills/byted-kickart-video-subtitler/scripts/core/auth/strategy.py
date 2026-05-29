# MIT License
#
# Copyright (c) 2026 ByteDance
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
from abc import ABC, abstractmethod
from functools import cache
from enum import Enum


class AuthType(Enum):
    AK_SK = "ak_sk"
    API_KEY = "api_key"


class AuthStrategy(ABC):
    """鉴权策略接口 (Strategy Pattern)"""

    @property
    @abstractmethod
    def strategy(self) -> AuthType:
        """获取当前使用的鉴权策略类型"""
        pass


class AkSkAuthStrategy(AuthStrategy):
    """AK/SK 鉴权策略"""

    @property
    def strategy(self) -> AuthType:
        return AuthType.AK_SK

    def __init__(self):
        self.ak = os.getenv("ACCESS_KEY_ID")
        self.sk = os.getenv("SECRET_ACCESS_KEY")

        if not self.ak or not self.sk:
            raise ValueError(
                "AK/SK未提供，且环境变量中未找到 ACCESS_KEY_ID/SECRET_ACCESS_KEY"
            )


class ApiKeyAuthStrategy(AuthStrategy):
    """API Key 鉴权策略"""

    @property
    def strategy(self) -> AuthType:
        return AuthType.API_KEY

    def __init__(self):
        self.api_key = os.getenv("ARK_SKILL_API_KEY")
        self.base_url = os.getenv("ARK_SKILL_API_BASE")

        if not self.api_key or not self.base_url:
            raise ValueError(
                "API Key/Base URL 未提供，且环境变量中未找到 ARK_SKILL_API_KEY/ARK_SKILL_API_BASE"
            )


class AuthStrategyFactory:
    """鉴权策略工厂 (Factory Pattern)"""

    @staticmethod
    @cache
    def create() -> AuthStrategy:
        if os.getenv("ARK_SKILL_API_BASE") and os.getenv("ARK_SKILL_API_KEY"):
            return ApiKeyAuthStrategy()
        if os.getenv("ACCESS_KEY_ID") and os.getenv("SECRET_ACCESS_KEY"):
            return AkSkAuthStrategy()
        raise Exception("鉴权凭证未配置(缺少 AK/SK 或 Token)")
