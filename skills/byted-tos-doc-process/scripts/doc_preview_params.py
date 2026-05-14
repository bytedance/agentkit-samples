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

#!/usr/bin/env python3
"""Shared helpers for TOS doc-preview scripts.

This module provides a small utility to translate high-level doc-preview
arguments into the exact `x-tos-*` HTTP query parameters required by TOS.

All scripts in this skill should use this function when generating
pre-signed URLs for doc-preview, so that query construction is consistent
and easy to maintain.
"""

from __future__ import annotations

import base64
from typing import Dict, Optional


_DEFAULT_PROCESS = "doc-preview"


def build_doc_preview_query_params(
    *,
    process: str = _DEFAULT_PROCESS,
    dest_type: Optional[str] = None,
    src_type: Optional[str] = None,
    page: Optional[int] = None,
    image_dpi: Optional[int] = None,
    image_quality: Optional[int] = None,
    img_mode: Optional[int] = None,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    image_params: Optional[str] = None,
    save_bucket: Optional[str] = None,
    save_object: Optional[str] = None,
) -> Dict[str, str]:
    """Build the query parameters for a doc-preview pre-signed URL.

    The returned dict is ready to be passed as the ``query`` argument to
    :meth:`tos.TosClientV2.pre_signed_url`.

    Mapping (see also REFERENCE.md and official doc-preview docs):

    - ``process``      -> ``x-tos-process`` (typically ``"doc-preview"``)
    - ``dest_type``    -> ``x-tos-doc-dst-type`` (pdf/png/jpg/html)
    - ``src_type``     -> ``x-tos-doc-src-type``
    - ``page``         -> ``x-tos-doc-page``
    - ``image_dpi``    -> ``x-tos-doc-image-dpi``
    - ``image_quality``-> ``x-tos-doc-image-quality``
    - ``img_mode``     -> ``image-mode``
    - ``start_page``   -> ``start-page``
    - ``end_page``     -> ``end-page``
    - ``image_params`` -> ``image-params``
    - ``save_bucket``  -> ``x-tos-save-bucket``
    - ``save_object``  -> ``x-tos-save-object``
    """

    params: Dict[str, str] = {}

    if process:
        params["x-tos-process"] = process

    if dest_type:
        params["x-tos-doc-dst-type"] = dest_type

    if src_type:
        params["x-tos-doc-src-type"] = src_type

    if page is not None:
        params["x-tos-doc-page"] = str(page)

    if image_dpi is not None:
        params["x-tos-doc-image-dpi"] = str(image_dpi)

    if image_quality is not None:
        params["x-tos-doc-image-quality"] = str(image_quality)

    if img_mode is not None:
        params["image-mode"] = str(img_mode)

    if start_page is not None:
        params["start-page"] = str(start_page)

    if end_page is not None:
        params["end-page"] = str(end_page)

    if image_params:
        params["image-params"] = image_params

    if save_bucket:
        params["x-tos-save-bucket"] = base64.urlsafe_b64encode(
            save_bucket.encode("utf-8")
        ).decode("utf-8")

    if save_object:
        # For query-based save-as, backend expects URL-safe base64 for object key.
        params["x-tos-save-object"] = base64.urlsafe_b64encode(
            save_object.encode("utf-8")
        ).decode("utf-8")

    return params
