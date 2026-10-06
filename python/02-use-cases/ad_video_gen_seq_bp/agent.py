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

import json
import logging
import os
import sys
from pathlib import Path

# Make this agent's own directory importable before anything local is imported.
# `veadk web` loads this file as the submodule `ad_video_gen_seq.agent`, which
# only puts the *parent* directory on sys.path, so bare imports like `app.*`
# would otherwise fail. Do NOT add the parent directory here: in the deployed
# container this project lives at /app, and putting its parent (/) on sys.path
# makes the project root itself resolve as a package named `app` (via the root
# __init__.py), shadowing the real app/ subpackage.
_AGENT_DIR = str(Path(__file__).resolve().parent)
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

# veadk resolves CLOUD_PROVIDER, endpoints, and credentials once at import
# time, so the environment must be fully populated before any veadk import
# below.
from consts import set_veadk_environment_variables  # noqa: E402

set_veadk_environment_variables()

from google.adk.models.lite_llm import LiteLlm  # noqa: E402
from veadk.models.ark_llm import ArkLlm  # noqa: E402

# It is recommended to set the global logger via logging.basicConfig; default log level is INFO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#### Model defaults

# veadk's built-in BytePlus fallbacks lag the current model generation
# (`seed-1-6-250915` for the agent LLM, Seedance 1.5 for video, Seedream 4.5
# for images), so a run without a `config.yaml` silently lands on very old
# models. veadk has already flattened `config.yaml` / `.env` into os.environ
# during its import above, so filling in defaults with setdefault here keeps
# the documented precedence: environment > config.yaml > these defaults.
# `settings.model` snapshotted its values before these defaults existed, so
# rebuild it afterwards; the sub-agents read it when `app` is imported below.
import veadk.config as _veadk_config  # noqa: E402

for _key, _value in {
    "MODEL_AGENT_NAME": "dola-seed-2-1-turbo-260628",
    "MODEL_EVALUATE_NAME": "dola-seed-2-1-turbo-260628",
    "MODEL_IMAGE_NAME": "dola-seedream-5-0-pro-260628",
    "MODEL_VIDEO_NAME": "dreamina-seedance-2-5-260628",  # Seedance 2.5
    # Endpoints too: veadk resolved its BytePlus-vs-mainland default off
    # CLOUD_PROVIDER when it was first imported, which under `veadk web`
    # happens before consts.py runs -- leaving a run without a `config.yaml`
    # pointed at ark.cn-beijing.volces.com, where a BytePlus ARK key fails
    # with `401 AuthenticationError: The API key doesn't exist`.
    "MODEL_AGENT_API_BASE": "https://ark.ap-southeast.bytepluses.com/api/v3",
    "MODEL_IMAGE_API_BASE": "https://ark.ap-southeast.bytepluses.com/api/v3",
    "MODEL_VIDEO_API_BASE": "https://ark.ap-southeast.bytepluses.com/api/v3",
}.items():
    os.environ.setdefault(_key, _value)

_veadk_config.settings.model = type(_veadk_config.settings.model)()

#### End of model defaults

#### Start of workaround

# The Dev UI's /dev/apps/{app}/build_graph endpoint serializes the agent's model
# with model_dump(mode="python") (see google/adk/cli/utils/graph_serialization.py),
# which leaves the live `llm_client` handle in the payload. FastAPI then fails to
# encode it as JSON and the endpoint returns 500. Marking the field as excluded
# keeps the client on the instance for generation while dropping it from every
# dump. Still required as of google-adk 2.2.0; recheck on future upgrades.
for _model_cls in (LiteLlm, ArkLlm):
    _field = _model_cls.model_fields.get("llm_client")
    if _field is not None and not _field.exclude:
        _field.exclude = True
        _model_cls.model_rebuild(force=True)

#### END OF WORKAROUND

#### Start of workaround

# The agent model occasionally emits tool-call arguments that are not strictly
# valid JSON (e.g. an unescaped quote inside a long image/video prompt).
# google-adk's _parse_tool_call_arguments only repairs unquoted object keys and
# otherwise re-raises, which aborts the entire workflow run with a
# JSONDecodeError. Still the case as of google-adk 2.6.2; recheck on upgrades.
# Fall back to json-repair, and log the raw payload so genuinely unrecoverable
# calls can be diagnosed instead of guessing at the model output.
import google.adk.models.lite_llm as _lite_llm  # noqa: E402
from json_repair import repair_json  # noqa: E402

_original_parse_tool_call_arguments = _lite_llm._parse_tool_call_arguments


def _parse_tool_call_arguments_with_repair(arguments):
    try:
        return _original_parse_tool_call_arguments(arguments)
    except json.JSONDecodeError:
        logger.warning(
            "Model produced malformed tool-call arguments, attempting repair: %r",
            arguments,
        )
        repaired = repair_json(arguments, return_objects=True)
        if isinstance(repaired, dict) and repaired:
            return repaired
        raise


_lite_llm._parse_tool_call_arguments = _parse_tool_call_arguments_with_repair

#### END OF WORKAROUND

#### Start of workaround

# The lite_llm patch above does not cover this pipeline's actual runtime path:
# every sub-agent sets `enable_responses=True`, so requests go through veadk's
# ArkLlm (Ark Responses API), where tool-call arguments are parsed with a bare
# `json.loads(output.arguments)` in event_to_generate_content_response
# (veadk/models/ark_llm.py). Malformed arguments (same failure mode as above)
# therefore still abort the whole run with a JSONDecodeError. Repair the
# arguments in place before veadk parses them; leave them untouched when repair
# fails so the original error still surfaces. Still required as of
# veadk-python 1.0.9; recheck on upgrades.
import veadk.models.ark_llm as _ark_llm  # noqa: E402

_original_event_to_generate_content_response = (
    _ark_llm.event_to_generate_content_response
)


def _repair_ark_function_call_arguments(event):
    # Only full responses carry `output`; stream delta events do not.
    for output in getattr(event, "output", None) or []:
        if not isinstance(output, _ark_llm.ResponseFunctionToolCall):
            continue
        arguments = output.arguments
        if not arguments:
            continue
        try:
            json.loads(arguments)
        except json.JSONDecodeError:
            logger.warning(
                "Model produced malformed Responses-API tool-call arguments, "
                "attempting repair: %r",
                arguments,
            )
            repaired = repair_json(arguments, return_objects=True)
            if isinstance(repaired, dict) and repaired:
                output.arguments = json.dumps(repaired, ensure_ascii=False)


def _event_to_generate_content_response_with_repair(*args, **kwargs):
    event = kwargs.get("event", args[0] if args else None)
    if event is not None:
        _repair_ark_function_call_arguments(event)
    return _original_event_to_generate_content_response(*args, **kwargs)


# Both veadk call sites (streaming and non-streaming) resolve this function
# through module globals at call time, so patching the attribute covers both.
_ark_llm.event_to_generate_content_response = (
    _event_to_generate_content_response_with_repair
)

#### END OF WORKAROUND

#### Start of workaround

# Every sub-agent in the sequential pipeline sees the full session history,
# including tool calls made by earlier agents (e.g. image_agent's
# image_generate). The model occasionally imitates one of those calls even
# though the tool is not in its own tool list, and google-adk's _get_tool then
# raises ValueError ("Tool 'X' not found"), aborting the entire run after the
# earlier (expensive) stages already completed. Return the error to the model
# as a normal tool response instead, so it can correct itself and continue.
# Still required as of google-adk 2.6.2; recheck on upgrades.
import google.adk.flows.llm_flows.functions as _adk_functions  # noqa: E402
from google.adk.tools.function_tool import FunctionTool  # noqa: E402

_original_get_tool = _adk_functions._get_tool


def _get_tool_with_fallback(function_call, tools_dict):
    try:
        return _original_get_tool(function_call, tools_dict)
    except ValueError:
        available = ", ".join(tools_dict.keys())
        logger.warning(
            "Model called unknown tool %r (available: %s); "
            "returning the error to the model instead of aborting the run",
            function_call.name,
            available,
        )
        error_msg = (
            f"Error: tool '{function_call.name}' does not exist for this agent. "
            f"The only tools you can call are: {available}. Do not repeat tool "
            "calls made by other agents earlier in the conversation. Continue "
            "the task using only your own tools."
        )

        def _unknown_tool():
            return {"error": error_msg}

        fallback = FunctionTool(func=_unknown_tool)
        # Match the hallucinated name so the function response pairs with the
        # model's function call.
        fallback.name = function_call.name
        return fallback


_adk_functions._get_tool = _get_tool_with_fallback

#### END OF WORKAROUND

# Import the sequential multi-agent pipeline only after the workarounds above
# are in place, so every sub-agent model is patched consistently.
from app import root_agent  # noqa: E402

# Auto-continue guard for the sub-agents whose job *is* a tool call. google-adk
# ends a sub-agent's turn as soon as its model replies without a tool call, so
# a model that narrates ("Generating the four first-frame images now...") or
# emits a result-shaped answer without actually calling image_generate /
# video_generate / evaluate_media / video_combine + upload_file_to_tos hands an
# incomplete result to the next stage of the sequential pipeline. The guard
# injects a `continue_pipeline` tool call whenever such a turn would end
# before the required tool(s) have run. See pipeline_guard.py.
import pipeline_guard  # noqa: E402

pipeline_guard.install_by_name(
    root_agent,
    {
        "image_agent": {"required_tools": {"image_generate"}},
        "image_evaluate_agent": {"required_tools": {"evaluate_media"}},
        "video_agent": {"required_tools": {"video_generate"}},
        "video_evaluate_agent": {"required_tools": {"evaluate_media"}},
        "release_agent": {"required_tools": {"video_combine", "upload_file_to_tos"}},
    },
)

# support veadk web
__all__ = ["root_agent"]
