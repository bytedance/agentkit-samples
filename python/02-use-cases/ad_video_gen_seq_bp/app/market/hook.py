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

import tempfile
import os
import re
import ipaddress
from typing import Optional, Tuple, List, Dict
import requests

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.run_config import StreamingMode
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.utils import upload_file_to_tos


def is_internal_ip(hostname: str) -> bool:
    """
    Check whether the hostname is an internal IP address (to prevent SSRF attacks)
    Args:
        hostname: hostname or IP address
    Returns:
        bool: True if it is an internal IP, otherwise False
    """
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def get_url_mime_type(url: str) -> Optional[str]:
    """
    Get the MIME type of a URL
    Args:
        url: the URL to check
    Returns:
        Optional[str]: the MIME type; None if it is not an image or detection failed
    """
    extension_to_mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "svg": "image/svg+xml",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "ico": "image/x-icon",
    }

    try:
        from urllib.parse import urlparse, unquote

        parsed = urlparse(url)
        path = unquote(parsed.path)

        extension = path.split(".")[-1].lower() if "." in path else ""
        if extension in extension_to_mime:
            return extension_to_mime[extension]

        response = requests.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get("Content-Type", "")

        if content_type:
            mime_type = content_type.split(";")[0].strip().lower()
            image_mime_types = [
                "image/jpeg",
                "image/png",
                "image/gif",
                "image/webp",
                "image/bmp",
                "image/svg+xml",
                "image/tiff",
                "image/x-icon",
            ]
            if mime_type in image_mime_types:
                return mime_type
        return None
    except Exception:
        return None


def is_safe_url(url: str) -> bool:
    """
    Check whether a URL is safe (not an internal IP)
    Args:
        url: the URL to check
    Returns:
        bool: True if the URL is safe, otherwise False
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False

        return not is_internal_ip(hostname)
    except Exception:
        return False


def process_urls_with_mime_types(text: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Process URLs in the text, extract image URLs and modify the text
    Args:
        text: the original text
    Returns:
        Tuple[List[Dict[str, str]], str]:
            - list of URLs, each item containing url and mime_type
            - the modified text (an "(image x)" marker is appended after each URL)
    """
    if not isinstance(text, str) or text.strip() == "":
        return [], text

    url_start_pattern = re.compile(r"https?://", re.IGNORECASE)

    urls = []
    for match in url_start_pattern.finditer(text):
        start_pos = match.start()
        url_pattern = re.compile(
            r"https?://"
            r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:[a-zA-Z]{2,6}\.?|[a-zA-Z0-9-]{2,}\.?)"
            r"(?::\d+)?"
            r"(?:/[a-zA-Z0-9\-._~%!$&\'()*+,;=:@/]*|/%[0-9A-Fa-f]{2})*"
            r"(?:\?[a-zA-Z0-9\-._~%!$&\'()*+,;=:@/?%]*)?",
            re.IGNORECASE,
        )
        url_match = url_pattern.match(text, start_pos)

        if url_match:
            url = url_match.group()
            if url not in urls:
                urls.append(url)

    image_urls = []
    modified_text = text
    image_idx = 0

    for url in urls:
        if not is_safe_url(url):
            continue

        mime_type = get_url_mime_type(url)
        if mime_type:
            image_idx += 1
            image_urls.append({"url": url, "mime_type": mime_type})
            modified_text = modified_text.replace(url, f"{url} (image {image_idx})")
        else:
            modified_text = modified_text.replace(url, f"{url} (detected as non-image)")

    return image_urls, modified_text


def hook_inline_data_transform(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    user_content = callback_context.user_content
    new_parts = []
    image_idx = 0

    for part in user_content.parts:
        if part.text:
            new_parts.append(
                types.Part(
                    text=part.text,
                )
            )
        if part.inline_data:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                tmp_file.write(part.inline_data.data)
                tmp_file_path = tmp_file.name

            try:
                file_uri = upload_file_to_tos(tmp_file_path)
                if file_uri:
                    image_idx += 1
                    new_parts.append(
                        types.Part(
                            text=f"Image URL: {file_uri}",
                        )
                    )

            finally:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)

    user_content.parts = new_parts


def hook_input_urls(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    callback_context.state["cb_agent_state"] = (
        "\n✅ Marketing strategy analysis complete; proceeding to storyboard design\n"
    )
    # before_agent_callback
    if callback_context.agent_name == "market_agent":
        new_parts = []
        # user_content = callback_context.user_content
        if len(llm_request.contents) > 0:
            for part in llm_request.contents[0].parts:
                if part.text:
                    url_list, new_text = process_urls_with_mime_types(part.text)
                    new_parts.append(
                        types.Part(
                            text=new_text,
                        )
                    )
                    for url in url_list:
                        new_parts.append(
                            types.Part(
                                file_data=types.FileData(
                                    mime_type=url["mime_type"], file_uri=url["url"]
                                )
                            )
                        )
            llm_request.contents[0].parts = new_parts

        # Check whether the number of images exceeds the limit
        image_parts_count = 0
        for part in llm_request.contents[0].parts:
            if part.file_data:
                image_parts_count += 1
            if part.inline_data:
                image_parts_count += 1

            if image_parts_count > 1:
                callback_context.state["end_invocation"] = True
                if callback_context.run_config.streaming_mode != StreamingMode.NONE:
                    return LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part(
                                    text="❌ You provided more than one image, which is not supported by this workflow. Please try again with a single image."
                                )
                            ],
                        ),
                        partial=True,
                    )
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text="❌ You provided more than one image, which is not supported by this workflow. Please try again with a single image."
                            )
                        ],
                    )
                )

    return None
