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

# adapted from Google ADK models adk-python/blob/main/src/google/adk/models/lite_llm.py at f1f44675e4a86b75e72cfd838efd8a0399f23e24 · google/adk-python

import base64
import json
import time
from typing import Any, Dict, Union, AsyncGenerator, Tuple, List, Optional, Literal
from typing_extensions import override

from google.adk.models import LlmRequest, LlmResponse, Gemini
from google.genai import types
from pydantic import Field, BaseModel
from volcenginesdkarkruntime import AsyncArk
from volcenginesdkarkruntime._streaming import AsyncStream
from volcenginesdkarkruntime.types.responses import (
    Response as ArkTypeResponse,
    ResponseStreamEvent,
    FunctionToolParam,
    ResponseTextConfigParam,
    ResponseReasoningItem,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseFunctionToolCall,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseTextDeltaEvent,
    ResponseCompletedEvent,
)
from volcenginesdkarkruntime.types.responses.response_input_message_content_list_param import (
    ResponseInputTextParam,
    ResponseInputImageParam,
    ResponseInputVideoParam,
    ResponseInputFileParam,
    ResponseInputContentParam,
)
from volcenginesdkarkruntime.types.responses.response_input_param import (
    ResponseInputItemParam,
    ResponseFunctionToolCallParam,
    EasyInputMessageParam,
    FunctionCallOutput,
)

from veadk.config import settings
from veadk.consts import DEFAULT_VIDEO_MODEL_API_BASE
from veadk.utils.logger import get_logger

logger = get_logger(__name__)


_ARK_TEXT_FIELD_TYPES = {"json_object", "json_schema"}

_FINISH_REASON_MAPPING = {
    "incomplete": {
        "length": types.FinishReason.MAX_TOKENS,
        "content_filter": types.FinishReason.SAFETY,
    },
    "completed": {
        "other": types.FinishReason.STOP,
    },
}

ark_supported_fields = [
    "input",
    "model",
    "stream",
    "background",
    "include",
    "instructions",
    "max_output_tokens",
    "parallel_tool_calls",
    "previous_response_id",
    "thinking",
    "store",
    "caching",
    "stream",
    "temperature",
    "text",
    "tool_choice",
    "tools",
    "top_p",
    "max_tool_calls",
    "expire_at",
    "extra_headers",
    "extra_query",
    "extra_body",
    "timeout",
    "reasoning"
    # auth params
    "api_key",
    "api_base",
]


def _to_ark_role(role: Optional[str]) -> Literal["user", "assistant"]:
    if role in ["model", "assistant"]:
        return "assistant"
    return "user"


def _safe_json_serialize(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, OverflowError):
        return str(obj)


def _schema_to_dict(schema: types.Schema | dict[str, Any]) -> dict:
    schema_dict = (
        schema.model_dump(exclude_none=True)
        if isinstance(schema, types.Schema)
        else dict(schema)
    )
    enum_values = schema_dict.get("enum")
    if isinstance(enum_values, (list, tuple)):
        schema_dict["enum"] = [value for value in enum_values if value is not None]

    if "type" in schema_dict and schema_dict["type"] is not None:
        t = schema_dict["type"]
        schema_dict["type"] = (t.value if isinstance(t, types.Type) else str(t)).lower()

    if "items" in schema_dict:
        items = schema_dict["items"]
        schema_dict["items"] = (
            _schema_to_dict(items) if isinstance(items, (types.Schema, dict)) else items
        )

    if "properties" in schema_dict:
        new_props = {}
        for key, value in schema_dict["properties"].items():
            if isinstance(value, (types.Schema, dict)):
                new_props[key] = _schema_to_dict(value)
            else:
                new_props[key] = value
        schema_dict["properties"] = new_props

    return schema_dict


# -----------------------------------------------------------------
# inputs param transform ------------------------------------------
def _file_data_to_content_param(
    part: types.Part,
) -> ResponseInputContentParam:
    file_uri = part.file_data.file_uri
    mime_type = part.file_data.mime_type
    fps = 1.0
    if getattr(part, "video_metadata", None):
        video_metadata = part.video_metadata
        if isinstance(video_metadata, dict):
            fps = video_metadata.get("fps")
        else:
            fps = getattr(video_metadata, "fps", 1)

    is_file_id = file_uri.startswith("file_id://")
    value = file_uri[10:] if is_file_id else file_uri
    # video
    if mime_type.startswith("video/"):
        param = {"file_id": value} if is_file_id else {"video_url": value}
        if fps is not None:
            param["fps"] = fps
        return ResponseInputVideoParam(
            type="input_video",
            **param,
        )
    # image
    if mime_type.startswith("image/"):
        return ResponseInputImageParam(
            type="input_image",
            detail="auto",
            **({"file_id": value} if is_file_id else {"image_url": value}),
        )
    # file
    param = {"file_id": value} if is_file_id else {"file_url": value}
    return ResponseInputFileParam(
        type="input_file",
        **param,
    )


def _inline_data_to_content_param(part: types.Part) -> ResponseInputContentParam:
    mime_type = (
        part.inline_data.mime_type if part.inline_data else None
    ) or "application/octet-stream"
    base64_string = base64.b64encode(part.inline_data.data).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{base64_string}"

    if mime_type.startswith("image"):
        return ResponseInputImageParam(
            type="input_image",
            image_url=data_uri,
            detail="auto",
        )
    if mime_type.startswith("video"):
        param: Dict[str, Any] = {"video_url": data_uri}
        if getattr(part, "video_metadata", None):
            video_metadata = part.video_metadata
            if isinstance(video_metadata, dict):
                fps = video_metadata.get("fps")
            else:
                fps = getattr(video_metadata, "fps", None)
            if fps is not None:
                param["fps"] = fps
        return ResponseInputVideoParam(
            type="input_video",
            **param,
        )

    file_param: Dict[str, Any] = {"file_data": data_uri}
    return ResponseInputFileParam(
        type="input_file",
        **file_param,
    )


def _get_content(
    parts: List[types.Part],
    role: Literal["user", "system", "developer", "assistant"],
) -> Optional[EasyInputMessageParam]:
    content = []
    for part in parts:
        if part.text:
            content.append(
                ResponseInputTextParam(
                    type="input_text",
                    text=part.text,
                )
            )
        elif part.inline_data and part.inline_data.data:
            content.append(_inline_data_to_content_param(part))
        elif part.file_data:  # file_id和file_url
            content.append(_file_data_to_content_param(part))
    if len(content) > 0:
        return EasyInputMessageParam(type="message", role=role, content=content)
    else:
        return None


def _content_to_input_item(
    content: types.Content,
) -> Union[ResponseInputItemParam, List[ResponseInputItemParam]]:
    role = _to_ark_role(content.role)

    # 1. FunctionResponse：`Tool` messages cannot be mixed with other content
    input_list = []
    for part in content.parts:
        if part.function_response:  # FunctionCallOutput
            input_list.append(
                FunctionCallOutput(
                    call_id=part.function_response.id,
                    output=_safe_json_serialize(part.function_response.response),
                    type="function_call_output",
                )
            )
    if input_list:
        return input_list if len(input_list) > 1 else input_list[0]

    input_content = _get_content(content.parts, role=role) or None

    if role == "user":
        # 2. Process the user's message
        if input_content:
            return input_content
    else:  # model
        # 3. Processing model messages
        for part in content.parts:
            if part.function_call:
                input_list.append(
                    ResponseFunctionToolCallParam(
                        arguments=_safe_json_serialize(part.function_call.args),
                        call_id=part.function_call.id,
                        name=part.function_call.name,
                        type="function_call",
                    )
                )
            elif part.text or part.inline_data:
                if input_content:
                    input_list.append(input_content)
    return input_list


def _function_declarations_to_tool_param(
    function_declaration: types.FunctionDeclaration,
) -> FunctionToolParam:
    assert function_declaration.name

    parameters = {"type": "object", "properties": {}}
    if function_declaration.parameters and function_declaration.parameters.properties:
        properties = {}
        for key, value in function_declaration.parameters.properties.items():
            properties[key] = _schema_to_dict(value)

        parameters = {
            "type": "object",
            "properties": properties,
        }
    elif function_declaration.parameters_json_schema:
        parameters = function_declaration.parameters_json_schema

    tool_params = FunctionToolParam(
        name=function_declaration.name,
        parameters=parameters,
        type="function",
        description=function_declaration.description,
    )

    return tool_params


def _responses_schema_to_text(
    response_schema: types.SchemaUnion,
) -> Optional[ResponseTextConfigParam | dict]:
    schema_name = ""
    if isinstance(response_schema, dict):
        schema_type = response_schema.get("type")
        if (
            isinstance(schema_type, str)
            and schema_type.lower() in _ARK_TEXT_FIELD_TYPES
        ):
            return response_schema
        schema_dict = dict(response_schema)
    elif isinstance(response_schema, type) and issubclass(response_schema, BaseModel):
        schema_name = response_schema.__name__
        schema_dict = response_schema.model_json_schema()
    elif isinstance(response_schema, BaseModel):
        if isinstance(response_schema, types.Schema):
            # GenAI Schema instances already represent JSON schema definitions.
            schema_name = response_schema.__name__
            schema_dict = response_schema.model_dump(exclude_none=True, mode="json")
        else:
            schema_name = response_schema.__name__
            schema_dict = response_schema.__class__.model_json_schema()
    elif hasattr(response_schema, "model_dump"):
        schema_name = response_schema.__name__
        schema_dict = response_schema.model_dump(exclude_none=True, mode="json")
    else:
        logger.warning(
            "Unsupported response_schema type %s for LiteLLM structured outputs.",
            type(response_schema),
        )
        return None

    return ResponseTextConfigParam(
        format={  # noqa
            "type": "json_schema",
            "name": schema_name,
            "schema": schema_dict,
            "strict": True,
        }
    )


def _get_responses_inputs(
    llm_request: LlmRequest,
) -> Tuple[
    Optional[str],
    Optional[List[ResponseInputItemParam]],
    Optional[List[FunctionToolParam]],
    Optional[ResponseTextConfigParam],
    Optional[Dict],
]:
    # 0. instructions(system prompt)
    instructions: Optional[str] = None
    if llm_request.config and llm_request.config.system_instruction:
        instructions = llm_request.config.system_instruction
    # 1. input
    input_params: Optional[List[ResponseInputItemParam]] = []
    for content in llm_request.contents or []:
        # Each content represents `one conversation`.
        # This `one conversation` may contain `multiple pieces of content`,
        # but it cannot contain `multiple conversations`.
        input_item_or_list = _content_to_input_item(content)
        if isinstance(input_item_or_list, list):
            input_params.extend(input_item_or_list)
        elif input_item_or_list:
            input_params.append(input_item_or_list)

    # 2. Convert tool declarations
    tools: Optional[List[FunctionToolParam]] = None
    if (
        llm_request.config
        and llm_request.config.tools
        and llm_request.config.tools[0].function_declarations
    ):
        tools = [
            _function_declarations_to_tool_param(tool)
            for tool in llm_request.config.tools[0].function_declarations
        ]

    # 3. Handle `output-schema` -> `text`
    text: Optional[ResponseTextConfigParam] = None
    if llm_request.config and llm_request.config.response_schema:
        text = _responses_schema_to_text(llm_request.config.response_schema)

    # 4. Extract generation parameters
    generation_params: Optional[Dict] = None
    if llm_request.config:
        config_dict = llm_request.config.model_dump(exclude_none=True)
        generation_params = {}
        for key in ("temperature", "max_output_tokens", "top_p"):
            if key in config_dict:
                generation_params[key] = config_dict[key]

        if not generation_params:
            generation_params = None
    return instructions, input_params, tools, text, generation_params


def get_model_without_provider(request_data: dict) -> dict:
    model = request_data.get("model")

    if not isinstance(model, str):
        raise ValueError(
            "Unsupported Responses API request: 'model' must be a string in the OpenAI-style format, e.g. 'openai/gpt-4o'."
        )

    if "/" not in model:
        raise ValueError(
            "Unsupported Responses API request: only OpenAI-style model names are supported (use 'openai/<model>')."
        )

    provider, actual_model = model.split("/", 1)
    if provider != "openai":
        raise ValueError(
            f"Unsupported model prefix '{provider}'. Responses API request format only supports 'openai/<model>'."
        )

    request_data["model"] = actual_model

    return request_data


def filtered_inputs(
    inputs: List[ResponseInputItemParam],
) -> List[ResponseInputItemParam]:
    # Keep the first message and all consecutive user messages from the end
    # Collect all consecutive user messages from the end
    new_inputs = []
    for m in reversed(inputs):  # Skip the first message
        if m.get("type") == "function_call_output" or m.get("role") == "user":
            new_inputs.append(m)
        else:
            break  # Stop when we encounter a non-user message

    return new_inputs[::-1]


def _is_caching_enabled(request_data: dict) -> bool:
    extra_body = request_data.get("extra_body")
    if not isinstance(extra_body, dict):
        return False
    caching = extra_body.get("caching")
    if not isinstance(caching, dict):
        return False
    return caching.get("type") == "enabled"


def _remove_caching(request_data: dict) -> None:
    extra_body = request_data.get("extra_body")
    if isinstance(extra_body, dict):
        extra_body.pop("caching", None)
    request_data.pop("caching", None)


def request_reorganization_by_ark(request_data: Dict) -> Dict:
    # 1. model provider
    request_data = get_model_without_provider(request_data)

    # 2. filtered input
    request_data["input"] = filtered_inputs(request_data["input"])

    # 3. filter not support data
    request_data = {
        key: value for key, value in request_data.items() if key in ark_supported_fields
    }

    extra_body = request_data.get("extra_body")
    if not isinstance(extra_body, dict):
        extra_body = {}
        request_data["extra_body"] = extra_body
    extra_body["expire_at"] = int(time.time()) + 259200

    # [Note: Ark Limitations] caching and text
    # After enabling caching, output_schema(text) cannot be used. Caching must be disabled.
    if _is_caching_enabled(request_data) and request_data.get("text") is not None:
        logger.warning(
            "Caching is enabled, but text is provided. Ark does not support caching with text. Caching will be disabled."
        )
        _remove_caching(request_data)

    # [Note: Ark Limitations] tools and previous_response_id
    # Remove tools in subsequent rounds (when previous_response_id is present)
    if (
        "tools" in request_data
        and "previous_response_id" in request_data
        and request_data["previous_response_id"] is not None
    ):
        # Remove tools in subsequent rounds regardless of caching status
        del request_data["tools"]

    # [Note: Ark Limitations] caching and store
    # Ensure store field is true or default when caching is enabled
    if _is_caching_enabled(request_data):
        # Set store to true when caching is enabled for writing
        if "store" not in request_data:
            request_data["store"] = True
        elif request_data["store"] is False:
            # Override false to true for cache writing
            request_data["store"] = True

    # [NOTE Ark Limitations] instructions -> input (because of caching)
    # Due to the Volcano Ark settings, there is a conflict between the cache and the instructions field.
    # If a system prompt is needed, it should be placed in the system role message within the input, instead of using the instructions parameter.
    # https://www.volcengine.com/docs/82379/1585128
    instructions: Optional[str] = request_data.pop("instructions", None)
    if instructions and not request_data.get("previous_response_id"):
        request_data["input"].insert(
            0,
            EasyInputMessageParam(
                role="system",
                type="message",
                content=[
                    ResponseInputTextParam(
                        type="input_text",
                        text=instructions,
                    )
                ],
            ),
        )

    return request_data


# ---------------------------------------
# output transfer -----------------------
def event_to_generate_content_response(
    event: Union[ArkTypeResponse, ResponseStreamEvent],
    *,
    is_partial: bool = False,
    model_version: str = None,
) -> Optional[LlmResponse]:
    parts = []
    if not is_partial:
        for output in event.output:
            if isinstance(output, ResponseReasoningItem):
                parts.append(
                    types.Part(
                        text="\n".join([summary.text for summary in output.summary]),
                        thought=True,
                    )
                )
            elif isinstance(output, ResponseOutputMessage):
                text = ""
                if isinstance(output.content, list):
                    for item in output.content:
                        if isinstance(item, ResponseOutputText):
                            text += item.text
                parts.append(types.Part(text=text))

            elif isinstance(output, ResponseFunctionToolCall):
                part = types.Part.from_function_call(
                    name=output.name, args=json.loads(output.arguments or "{}")
                )
                part.function_call.id = output.call_id
                parts.append(part)

    else:
        if isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
            parts.append(types.Part(text=event.delta, thought=True))
        elif isinstance(event, ResponseTextDeltaEvent):
            parts.append(types.Part.from_text(text=event.delta))
        elif isinstance(event, ResponseCompletedEvent):
            raw_response = event.response
            llm_response = ark_response_to_generate_content_response(raw_response)
            return llm_response
        else:
            return None
    return LlmResponse(
        content=types.Content(role="model", parts=parts),
        partial=is_partial,
        model_version=model_version,
    )


def ark_response_to_generate_content_response(
    raw_response: ArkTypeResponse,
) -> LlmResponse:
    """
    ArkTypeResponse -> LlmResponse
    instead of `_model_response_to_generate_content_response`,
    """
    outputs = raw_response.output
    status = raw_response.status
    incomplete_details = getattr(
        raw_response.incomplete_details or None, "reason", "other"
    )

    finish_reason = _FINISH_REASON_MAPPING.get(status, {}).get(
        incomplete_details, types.FinishReason.OTHER
    )

    if not outputs:
        raise ValueError("No message in response")

    llm_response = event_to_generate_content_response(
        raw_response, model_version=raw_response.model, is_partial=False
    )
    llm_response.finish_reason = finish_reason
    if raw_response.usage:
        llm_response.usage_metadata = types.GenerateContentResponseUsageMetadata(
            prompt_token_count=raw_response.usage.input_tokens,
            candidates_token_count=raw_response.usage.output_tokens,
            total_token_count=raw_response.usage.total_tokens,
            cached_content_token_count=raw_response.usage.input_tokens_details.cached_tokens,
        )

    # previous_response_id
    llm_response.interaction_id = raw_response.id

    return llm_response


class ArkLlmClient:
    async def aresponse(
        self, **kwargs
    ) -> Union[ArkTypeResponse, AsyncStream[ResponseStreamEvent]]:
        # 1. Get request params
        api_base = kwargs.pop("api_base", DEFAULT_VIDEO_MODEL_API_BASE)
        api_key = kwargs.pop("api_key", settings.model.api_key)

        # 2. Call openai responses
        client = AsyncArk(
            base_url=api_base,
            api_key=api_key,
        )

        raw_response = await client.responses.create(**kwargs)
        return raw_response


class ArkLlm(Gemini):
    model: str
    llm_client: ArkLlmClient = Field(default_factory=ArkLlmClient)
    _additional_args: Dict[str, Any] = None
    use_interactions_api: bool = True

    def __init__(self, **kwargs):
        # adk version check
        if "previous_interaction_id" not in LlmRequest.model_fields:
            raise ImportError(
                "If using the ResponsesAPI, "
                "please upgrade the version of google-adk to `1.21.0` or higher with the command: "
                "`pip install -U 'google-adk>=1.21.0'`"
            )
        super().__init__(**kwargs)
        drop_params = kwargs.pop("drop_params", None)
        self._additional_args = dict(kwargs)
        self._additional_args.pop("llm_client", None)
        self._additional_args.pop("messages", None)
        self._additional_args.pop("tools", None)
        self._additional_args.pop("stream", None)
        if drop_params is not None:
            self._additional_args["drop_params"] = drop_params

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Generates content asynchronously.

        Args:
          llm_request: LlmRequest, the request to send to the LiteLlm model.
          stream: bool = False, whether to do streaming call.

        Yields:
          LlmResponse: The model response.
        """
        self._maybe_append_user_content(llm_request)
        # logger.debug(_build_request_log(llm_request))

        instructions, input_param, tools, text_format, generation_params = (
            _get_responses_inputs(llm_request)
        )

        if "functions" in self._additional_args:
            # LiteLLM does not support both tools and functions together.
            tools = None
        # ------------------------------------------------------ #
        # get previous_response_id
        previous_response_id = None
        if llm_request.previous_interaction_id:
            previous_response_id = llm_request.previous_interaction_id
        responses_args = {
            "model": self.model,
            "instructions": instructions,
            "input": input_param,
            "tools": tools,
            "text": text_format,
            "previous_response_id": previous_response_id,  # supply previous_response_id
        }
        # ------------------------------------------------------ #
        responses_args.update(self._additional_args)

        if generation_params:
            responses_args.update(generation_params)

        responses_args = request_reorganization_by_ark(responses_args)

        if stream:
            responses_args["stream"] = True
            async for part in await self.llm_client.aresponse(**responses_args):
                llm_response = event_to_generate_content_response(
                    event=part, is_partial=True, model_version=self.model
                )
                if llm_response:
                    yield llm_response
        else:
            raw_response = await self.llm_client.aresponse(**responses_args)
            llm_response = ark_response_to_generate_content_response(raw_response)
            yield llm_response

    @classmethod
    @override
    def supported_models(cls) -> list[str]:
        return [
            # For OpenAI models (e.g., "openai/gpt-4o")
            r"openai/.*",
        ]
