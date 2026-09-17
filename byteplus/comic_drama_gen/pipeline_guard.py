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

"""Auto-continue guard: keep a multi-step agent running until its job is done.

Why this exists
---------------
google-adk ends an agent's turn as soon as the model returns a response that
contains no function call (see ``Event.is_final_response``). Models driving a
multi-step tool pipeline fairly often narrate progress as a stand-alone,
text-only reply — "Here is the reference image, now generating the video!" or
"Step 5 complete, moving on to Step 6" — without issuing the next tool call in
that same response. The turn ends right there and the user has to type
"continue" to get the pipeline going again (or, inside an automated
multi-agent pipeline, a downstream agent receives an incomplete result).

What this does
--------------
* ``track_tool_use`` (an ``after_tool_callback``) records, per invocation,
  which tools the agent has actually called.
* ``auto_continue`` (an ``after_model_callback``) inspects every complete
  (non-partial) model response. If it contains no function call and the
  agent's job does not look finished, the callback appends a synthetic call
  to the ``continue_pipeline`` tool. That keeps the ADK loop alive: the tool
  result tells the model to carry on with the next step immediately.

"Finished" is decided by whichever of these you configure in ``install()``:

* ``required_tools`` — the reply is accepted once every listed tool has been
  called at least once during this invocation (e.g. ``{"video_generate"}``
  for an agent whose deliverable is a generated video).
* ``completion_markers`` — the reply is accepted if its visible text
  contains one of these strings (e.g. a final report heading). When only
  markers are configured the guard arms itself once the agent has called at
  least one tool in the invocation, so plain conversational replies are never
  nudged. When both are configured, both must hold.

In every mode a reply whose last line asks the user a question is accepted
(a genuine "I need your decision" pause), and the nudge is issued at most once
per text-only streak — if the model answers the nudge with another text-only
reply, that reply is accepted and the turn ends. A hard per-invocation cap is
a second safety net against loops.

The injected call/response pair is serialized like any other tool exchange:
an ``assistant`` message with ``tool_calls`` followed by a ``tool`` message
for OpenAI-compatible chat endpoints (LiteLlm), and ``function_call`` /
``function_call_output`` items for the Ark Responses API (ArkLlm) — verified
against ARK for both the cached (``previous_response_id``) and the replay
path. The id deliberately avoids ADK's ``adk-`` prefix, which ADK strips
before sending.

Usage
-----
    import pipeline_guard
    pipeline_guard.install(agent, required_tools={"video_generate"})

    # multi-agent trees: configure sub-agents by name
    pipeline_guard.install_by_name(root_agent, {
        "image_agent": {"required_tools": {"image_generate"}},
        "video_agent": {"required_tools": {"video_generate"}},
    })
"""

from __future__ import annotations

import logging
import uuid
from collections import OrderedDict
from typing import Any, Iterable, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.tools import BaseTool, FunctionTool, ToolContext
from google.genai import types

logger = logging.getLogger(__name__)

CONTINUE_TOOL_NAME = "continue_pipeline"

# Hard cap on nudges per (agent, invocation), purely as a safety net.
MAX_NUDGES_PER_INVOCATION = 40

DEFAULT_NUDGE_MESSAGE = (
    "⚠️ AUTO-CONTINUE GUARD: your previous message ended the turn without a "
    "tool call, but your task is not finished yet{missing}. The user must NOT "
    "have to type 'continue' to get the next step started. Proceed with the "
    "next step RIGHT NOW by calling the required tool — do not re-summarize "
    "what you already did. Only if the task is genuinely finished, or you are "
    "blocked on a decision that only the user can make, reply with a short "
    "message that says so explicitly."
)


class _InvocationState:
    __slots__ = ("tools_called", "nudged_since_last_tool", "nudges")

    def __init__(self) -> None:
        self.tools_called: set[str] = set()
        self.nudged_since_last_tool = False
        self.nudges = 0


class _Guard:
    """Per-agent guard configuration + per-invocation bookkeeping."""

    _MAX_TRACKED = 128

    def __init__(
        self,
        agent_name: str,
        required_tools: Iterable[str],
        completion_markers: Iterable[str],
        activate_on_tool_use: bool,
        nudge_message: str,
        max_nudges: int,
    ) -> None:
        self.agent_name = agent_name
        self.required_tools = frozenset(required_tools)
        self.completion_markers = tuple(m.lower() for m in completion_markers)
        self.activate_on_tool_use = activate_on_tool_use
        self.nudge_message = nudge_message
        self.max_nudges = max_nudges
        self._states: "OrderedDict[str, _InvocationState]" = OrderedDict()

    # -- bookkeeping ---------------------------------------------------------

    def _state_for(self, invocation_id: str) -> _InvocationState:
        state = self._states.get(invocation_id)
        if state is None:
            state = _InvocationState()
            self._states[invocation_id] = state
            while len(self._states) > self._MAX_TRACKED:
                self._states.popitem(last=False)
        else:
            self._states.move_to_end(invocation_id)
        return state

    # -- callbacks -----------------------------------------------------------

    def track_tool_use(
        self,
        tool: BaseTool,
        args: dict[str, Any],
        tool_context: ToolContext,
        tool_response: Any,
    ) -> Optional[dict]:
        """after_tool_callback: remember which tools ran this invocation."""
        if tool.name == CONTINUE_TOOL_NAME:
            return None
        state = self._state_for(tool_context.invocation_id)
        state.tools_called.add(tool.name)
        state.nudged_since_last_tool = False
        return None

    def auto_continue(
        self, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        """after_model_callback: keep the ADK loop alive until the job is done."""
        if llm_response.partial or llm_response.error_code:
            return None
        content = llm_response.content
        if content is None or not content.parts:
            return None
        if any(p.function_call for p in content.parts):
            return None

        state = self._state_for(callback_context.invocation_id)
        if self.activate_on_tool_use and not state.tools_called:
            return None
        if state.nudged_since_last_tool:
            logger.info(
                "[pipeline_guard:%s] model ended the turn again after a nudge; "
                "letting it stop",
                self.agent_name,
            )
            return None
        if state.nudges >= self.max_nudges:
            logger.warning(
                "[pipeline_guard:%s] nudge cap (%d) reached for invocation %s",
                self.agent_name,
                self.max_nudges,
                callback_context.invocation_id,
            )
            return None

        text = _visible_text(content)
        missing = sorted(self.required_tools - state.tools_called)
        if self._looks_finished(text, missing):
            return None

        state.nudged_since_last_tool = True
        state.nudges += 1
        logger.info(
            "[pipeline_guard:%s] text-only response before the job is done "
            "(missing tools: %s, nudge %d); injecting %s call",
            self.agent_name,
            missing or "-",
            state.nudges,
            CONTINUE_TOOL_NAME,
        )

        altered = llm_response.model_copy(deep=True)
        assert altered.content is not None and altered.content.parts is not None
        altered.content.parts.append(
            types.Part(
                function_call=types.FunctionCall(
                    # Not "adk-…": ADK strips those ids before the request is
                    # sent, and the endpoint wants a stable id on both the
                    # call and its result.
                    id=f"call_autocontinue_{uuid.uuid4().hex[:12]}",
                    name=CONTINUE_TOOL_NAME,
                    args={},
                )
            )
        )
        return altered

    def _looks_finished(self, text: str, missing_tools: list[str]) -> bool:
        lowered = text.lower()
        tools_ok = not missing_tools
        markers_ok = not self.completion_markers or any(
            marker in lowered for marker in self.completion_markers
        )
        if (self.required_tools or self.completion_markers) and tools_ok and markers_ok:
            return True
        # A message that ends by asking the user something is a legitimate
        # pause (missing input, a confirmation, a choice only they can make).
        last_line = ""
        for line in reversed(text.strip().splitlines()):
            if line.strip():
                last_line = line.strip()
                break
        return "?" in last_line

    def nudge_text(self, tool_context: ToolContext) -> str:
        state = self._state_for(tool_context.invocation_id)
        missing = sorted(self.required_tools - state.tools_called)
        detail = f" (you still have to call: {', '.join(missing)})" if missing else ""
        return self.nudge_message.replace("{missing}", detail)


def _visible_text(content: types.Content) -> str:
    """Text the user actually sees (excludes reasoning/thought parts)."""
    chunks = []
    for part in content.parts or []:
        if part.text and not getattr(part, "thought", False):
            chunks.append(part.text)
    return "\n".join(chunks)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def install(
    agent,
    *,
    required_tools: Iterable[str] = (),
    completion_markers: Iterable[str] = (),
    activate_on_tool_use: Optional[bool] = None,
    nudge_message: str = DEFAULT_NUDGE_MESSAGE,
    max_nudges: int = MAX_NUDGES_PER_INVOCATION,
) -> _Guard:
    """Attach the guard (tool + callbacks) to a google-adk / veadk LlmAgent.

    Args:
        agent: The LlmAgent to guard (must have ``tools``).
        required_tools: Tool names that must all have been called during the
            invocation before a text-only reply is accepted as final.
        completion_markers: Substrings whose presence in the visible reply
            text marks the job as finished.
        activate_on_tool_use: Only start guarding after the agent has called
            at least one tool this invocation. Defaults to True when no
            ``required_tools`` are given (marker mode), False otherwise.
        nudge_message: Text returned by ``continue_pipeline``; ``{missing}``
            is replaced with the list of required tools not yet called.
        max_nudges: Hard cap on nudges per invocation.
    """
    if activate_on_tool_use is None:
        activate_on_tool_use = not required_tools
    guard = _Guard(
        agent_name=agent.name,
        required_tools=required_tools,
        completion_markers=completion_markers,
        activate_on_tool_use=activate_on_tool_use,
        nudge_message=nudge_message,
        max_nudges=max_nudges,
    )

    def continue_pipeline(tool_context: ToolContext) -> str:
        """Runtime-internal tool used by the auto-continue guard.

        The guard calls this automatically when a turn ends before the task is
        finished. You never need to call it yourself.
        """
        return guard.nudge_text(tool_context)

    if not any(getattr(t, "name", None) == CONTINUE_TOOL_NAME for t in agent.tools):
        agent.tools.append(FunctionTool(continue_pipeline))

    # ADK stops running after_tool_callbacks at the first one that returns a
    # value, and several agents already have callbacks that return the tool
    # response — so the tracker (which always returns None) goes first.
    agent.after_tool_callback = [guard.track_tool_use] + _as_list(
        agent.after_tool_callback
    )
    # Existing after_model_callbacks keep priority; ours runs last.
    agent.after_model_callback = _as_list(agent.after_model_callback) + [
        guard.auto_continue
    ]
    logger.info(
        "[pipeline_guard] installed on agent %r (required_tools=%s, "
        "completion_markers=%s, activate_on_tool_use=%s)",
        agent.name,
        sorted(guard.required_tools) or "-",
        list(guard.completion_markers) or "-",
        activate_on_tool_use,
    )
    return guard


def iter_agents(agent):
    """Yield ``agent`` and every descendant reachable through ``sub_agents``."""
    yield agent
    for sub in getattr(agent, "sub_agents", None) or []:
        yield from iter_agents(sub)


def install_by_name(root_agent, config: dict[str, dict]) -> dict[str, _Guard]:
    """Install guards on agents in a tree, selected by ``agent.name``.

    ``config`` maps an agent name to the keyword arguments for ``install``.
    Names that do not appear in the tree are reported with a warning so a
    typo does not silently disable the guard.
    """
    installed: dict[str, _Guard] = {}
    for agent in iter_agents(root_agent):
        kwargs = config.get(agent.name)
        if kwargs is None or agent.name in installed:
            continue
        if not hasattr(agent, "tools"):
            logger.warning(
                "[pipeline_guard] agent %r has no tools attribute; skipping",
                agent.name,
            )
            continue
        installed[agent.name] = install(agent, **kwargs)
    for name in config:
        if name not in installed:
            logger.warning(
                "[pipeline_guard] no agent named %r found under %r; guard not installed",
                name,
                root_agent.name,
            )
    return installed
