#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Render markdown for a media item under a chosen client style.

Three styles, selected by the launcher per client (see --media-style):

- codex (default): `![alt](forward-slash path)` — Codex Desktop renders this as an inline
  image/video preview. This is the skill's original, validated format; unchanged by default.
- link: `[alt](file:// or http url)` — a clickable hyperlink for clients that linkify markdown
  links in the visible reply (e.g. Claude Code) but do not inline-embed local media.
- both: emit both lines (Codex gets the inline preview, others get a clickable link).

Backslash Windows paths are never valid markdown URLs; the link form percent-encodes spaces /
non-ASCII via urllib so paths like ".../a b/草莓.mp4" do not break.
"""

from __future__ import annotations

from urllib.request import pathname2url


def _is_url(target: str) -> bool:
    return target.startswith(("http://", "https://", "file://"))


def _forward_slash(target: str) -> str:
    """Bare path with forward slashes (Codex embed form). No-op on URLs / POSIX paths."""
    return target.replace("\\", "/")


def _href(target: str) -> str:
    """A real URL for the link form: pass through http(s)/file URLs, else build a file:// URL
    with proper percent-encoding for spaces and non-ASCII characters."""
    if _is_url(target):
        return target.replace("\\", "/")
    return "file:" + pathname2url(target)


def media_markdown(alt: str, target, *, style: str = "codex") -> str:
    """Return the markdown snippet (no trailing newline) for one media item."""
    target = str(target)
    embed = f"![{alt}]({_forward_slash(target)})"
    link = f"[{alt}]({_href(target)})"
    if style == "link":
        return link
    if style == "both":
        return f"{embed}\n{link}"
    return embed  # codex (default)
