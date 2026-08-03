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

import os
from abc import ABC, abstractmethod
from functools import cache
from enum import Enum

class AuthType(Enum):
    AK_SK = "ak_sk"

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
            raise ValueError("AK/SK未提供，且环境变量中未找到 ACCESS_KEY_ID/SECRET_ACCESS_KEY")

class AuthStrategyFactory:
    """鉴权策略工厂 (Factory Pattern)"""
    @staticmethod
    @cache
    def create() -> AuthStrategy:
        if os.getenv("ACCESS_KEY_ID") and os.getenv("SECRET_ACCESS_KEY"):
            return AkSkAuthStrategy()
        raise Exception("鉴权凭证未配置 (缺少 AK/SK)")