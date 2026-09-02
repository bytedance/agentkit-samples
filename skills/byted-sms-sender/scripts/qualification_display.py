# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
"""Presentation adapters for the local qualification wizard."""

from __future__ import annotations

import json
import sys
import webbrowser
from dataclasses import dataclass
from typing import Callable, TextIO

from qualification_upload import QualificationUploadError


PresentCallback = Callable[[str], None]


@dataclass(frozen=True)
class QualificationDisplayAdapter:
    """Present one private loopback URL without owning wizard state."""

    name: str
    allows_embedding: bool
    present_callback: PresentCallback

    def present(self, url: str) -> None:
        self.present_callback(url)


def browser_display_adapter() -> QualificationDisplayAdapter:
    def present(url: str) -> None:
        if not webbrowser.open(url, new=1, autoraise=True):
            raise QualificationUploadError(
                "browser_unavailable", "Unable to open the local qualification form."
            )

    return QualificationDisplayAdapter("browser", False, present)


def host_display_adapter(
    *, output: TextIO = sys.stderr
) -> QualificationDisplayAdapter:
    def present(url: str) -> None:
        event = {
            "event": "qualification_display",
            "mode": "host",
            "url": url,
            "sensitive": True,
            "action": "open_private_loopback_url",
        }
        output.write(
            "QUALIFICATION_DISPLAY "
            + json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )
        output.flush()

    return QualificationDisplayAdapter("host", True, present)


def callback_display_adapter(
    callback: PresentCallback,
    *,
    name: str,
    allows_embedding: bool,
) -> QualificationDisplayAdapter:
    return QualificationDisplayAdapter(name, allows_embedding, callback)


def qualification_display_adapter(mode: str) -> QualificationDisplayAdapter:
    if mode == "browser":
        return browser_display_adapter()
    if mode == "host":
        return host_display_adapter()
    raise QualificationUploadError(
        "qualification_display_invalid", "Unsupported qualification display mode."
    )
