"""Authentication strategy module for Kickart API."""

import os
from enum import Enum


class AuthType(Enum):
    AK_SK = "ak_sk"


class AuthStrategy:
    """Authentication strategy holder."""

    def __init__(self, strategy: AuthType):
        self.strategy = strategy


class AuthStrategyFactory:
    """Factory to create authentication strategy based on environment."""

    @staticmethod
    def create() -> AuthStrategy:
        ak = os.getenv("KICKART_ACCESS_KEY") or os.getenv("ACCESS_KEY_ID", "")
        sk = os.getenv("KICKART_SECRET_KEY") or os.getenv("SECRET_ACCESS_KEY", "")

        if ak and sk:
            # Set the standard env vars that AkSkApiClient expects
            os.environ["ACCESS_KEY_ID"] = ak
            os.environ["SECRET_ACCESS_KEY"] = sk
            return AuthStrategy(AuthType.AK_SK)

        raise ValueError(
            "未配置有效的认证信息。请设置 KICKART_ACCESS_KEY/KICKART_SECRET_KEY 或 ACCESS_KEY_ID/SECRET_ACCESS_KEY 环境变量。"
        )
