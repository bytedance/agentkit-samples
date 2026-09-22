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

"""Signed-URL registry: undo model-side URL truncation before tools run.

Why this exists
---------------
image_generate / video_generate return pre-signed TOS URLs, e.g.
``https://ark-....volces.com/doubao-seedream-5-0-pro/.../x.jpeg?X-Tos-Algorithm=...&X-Tos-Signature=...``.
The signature lives in the query string, so the URL is only valid in full.
Despite the prompt forbidding it, models regularly copy such URLs into the
next tool call with the query string dropped or cut short (long opaque
strings are exactly what LLMs paraphrase), and TOS then answers ``403
Forbidden`` — which surfaces as a "permission" error in file_download or as
an image_generate/video_generate task failure.

What this does
--------------
* ``record_urls`` (an ``after_tool_callback``) walks every tool response and
  remembers each ``http(s)`` URL that carries a query string, keyed by
  ``scheme://host/path``.
* ``restore_urls`` (a ``before_tool_callback``) walks the arguments of the
  next tool call and, whenever it finds a stripped or truncated form of a
  recorded URL — as a bare argument, or embedded in a longer string such as
  a ``bash_tool`` command line or ``write_file_tool`` JSON content — replaces
  it in place with the recorded full URL. Unknown URLs are left untouched.

The registry is process-global and bounded; it only needs to survive for
the life of a session, and signed URLs expire within 24h anyway.
"""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from google.adk.tools import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 512
_URL_RE = re.compile(r"https?://[^\s\"'<>()\[\]]+")

# key = "scheme://host/path" -> full URL as returned by the tool
_registry: "OrderedDict[str, str]" = OrderedDict()


def _key(url: str) -> Optional[str]:
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def remember(url: str) -> None:
    """Record a full URL (only URLs with a query string are worth keeping)."""
    if "?" not in url:
        return
    key = _key(url)
    if key is None:
        return
    _registry[key] = url
    _registry.move_to_end(key)
    while len(_registry) > _MAX_ENTRIES:
        _registry.popitem(last=False)


def resolve(url: str) -> str:
    """Return the recorded full URL for a stripped/truncated ``url``.

    ``url`` is returned unchanged when it is not a URL, when nothing was
    recorded for its scheme+host+path, or when it already is the full URL.
    """
    if not isinstance(url, str):
        return url
    key = _key(url)
    if key is None:
        return url
    full = _registry.get(key)
    if full is None or full == url:
        return url
    # Accept: query stripped entirely, query truncated (prefix of the full
    # URL), or a differently-mangled query. In every case the exact
    # scheme+host+path match with a recorded signed URL is the strong signal.
    logger.warning("Restoring signed URL that the model altered: %r -> %r", url, full)
    return full


def _walk_record(obj: Any) -> None:
    if isinstance(obj, str):
        for match in _URL_RE.findall(obj):
            remember(match.rstrip(".,;"))
    elif isinstance(obj, dict):
        for value in obj.values():
            _walk_record(value)
    elif isinstance(obj, (list, tuple, set)):
        for value in obj:
            _walk_record(value)


_TRAILING_PUNCT = ".,;:!?"


def _restore_in_text(text: str, shell: bool = False) -> str:
    """Repair every URL embedded in ``text`` (bare URL, shell command, JSON,
    Markdown, ...) — the URL may be a whole tool argument or sit inside a
    longer string such as a ``bash_tool`` command or ``write_file_tool``
    content.

    With ``shell=True`` a repaired URL that is not already inside quotes is
    wrapped in single quotes: signed URLs contain ``&``, which an unquoted
    shell command line would treat as a background operator."""
    if "://" not in text:
        return text

    def _sub(match: "re.Match[str]") -> str:
        raw = match.group(0)
        core = raw.rstrip(_TRAILING_PUNCT)
        fixed = resolve(core)
        if fixed == core:
            return raw
        if shell:
            start = match.start()
            quoted = start > 0 and text[start - 1] in "'\""
            if not quoted:
                fixed = "'" + fixed + "'"
        return fixed + raw[len(core) :]

    return _URL_RE.sub(_sub, text)


def _walk_restore(obj: Any, shell: bool = False) -> Any:
    """Restore URLs in place where possible; return the (possibly new) value."""
    if isinstance(obj, str):
        return _restore_in_text(obj, shell=shell)
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            obj[k] = _walk_restore(v, shell=shell)
        return obj
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            obj[i] = _walk_restore(v, shell=shell)
        return obj
    return obj


_SHELL_TOOL_HINTS = ("bash", "shell", "terminal", "command", "exec")


def _is_shell_tool(tool: BaseTool) -> bool:
    name = (getattr(tool, "name", "") or "").lower()
    return any(hint in name for hint in _SHELL_TOOL_HINTS)


def record_urls(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Optional[dict]:
    """after_tool_callback: remember every signed URL a tool returned."""
    try:
        _walk_record(tool_response)
    except Exception:  # never let bookkeeping break the tool exchange
        logger.exception("url_registry: failed to record URLs from %s", tool.name)
    return None


def restore_urls(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """before_tool_callback: repair stripped/truncated URLs in tool args."""
    try:
        _walk_restore(args, shell=_is_shell_tool(tool))  # mutates in place
    except Exception:
        logger.exception("url_registry: failed to restore URLs for %s", tool.name)
    return None


def _as_list(cb: Any) -> list:
    if cb is None:
        return []
    return list(cb) if isinstance(cb, (list, tuple)) else [cb]


def install(agent) -> None:
    """Attach ``restore_urls`` / ``record_urls`` to ``agent``'s callbacks.

    Both callbacks always return ``None`` so they compose with existing
    callbacks; they are placed first so they run before anything else.
    """
    agent.before_tool_callback = [restore_urls] + _as_list(agent.before_tool_callback)
    agent.after_tool_callback = [record_urls] + _as_list(agent.after_tool_callback)
    logger.info("url_registry installed on agent %r", getattr(agent, "name", agent))
