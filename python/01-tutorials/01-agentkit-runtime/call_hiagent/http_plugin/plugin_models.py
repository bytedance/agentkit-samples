"""插件客户端的请求和回复格式。"""

import json
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class PluginRequest(BaseModel):
    message: str = Field(pattern=r"\S")
    streaming: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("streaming", "stream"),
        description="是否流式返回。兼容字段名 stream。",
    )
    user_id: str = "plugin_user"
    session_id: str = Field(default_factory=lambda: uuid4().hex)

    @model_validator(mode="before")
    @classmethod
    def decode_json_body(cls, body: object) -> object:
        # 部分插件客户端把整个 JSON 对象作为字符串发送。
        if isinstance(body, (str, bytes)):
            return json.loads(body)
        return body

    @field_validator("user_id", "session_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        # 两个 ID 既要放进请求头，也要能用作 URL 路径的一段。
        safe_header = value.isascii() and value.isprintable() and value == value.strip()
        safe_segment = (
            value not in {"", ".", ".."} and "/" not in value and "\\" not in value
        )
        if not (safe_header and safe_segment):
            raise ValueError("ID 必须是可用于请求头和路径的非空 ASCII 字符串")
        return value


class PluginReply(BaseModel):
    output: str
