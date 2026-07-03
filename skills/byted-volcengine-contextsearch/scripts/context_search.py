#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None


def require_requests():
    if requests is None:
        print("Error: Missing dependency 'requests'")
        print("Please install skill dependencies:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    return requests


def load_config() -> dict[str, Any]:
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        print(
            "Please copy config.json.template to config.json and fill in your API credentials"
        )
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def get_context_config(config: dict[str, Any], context_name: str) -> dict[str, Any]:
    contexts = config.get("contexts", {})
    if context_name not in contexts:
        print(f"Error: Context '{context_name}' not found in configuration")
        print(f"Available contexts: {', '.join(contexts.keys())}")
        sys.exit(1)

    return contexts[context_name]


def get_context_type(context_config: dict[str, Any]) -> str:
    raw_type = context_config.get("type")
    if raw_type is None:
        return "knowledge_base"
    if not isinstance(raw_type, str):
        raise ValueError("Context 'type' must be a string when provided")
    normalized = raw_type.strip().lower()
    if normalized == "":
        return "knowledge_base"
    if normalized in {"knowledge_base", "image", "video"}:
        return normalized
    raise ValueError("Context 'type' must be one of: knowledge_base, image, video")


def should_use_public_download_url(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host.endswith(".volces.com")


def search(
    base_url: str,
    api_key: str,
    text: str,
    mode: str | None = None,
    size: int | None = None,
    include_download_info: bool = False,
) -> dict[str, Any]:
    http = require_requests()
    url = f"{base_url}/v2/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload: dict[str, Any] = {"text": text}
    if mode is not None:
        payload["mode"] = mode
    if size is not None:
        payload["size"] = size
    if include_download_info:
        payload["return_download_info"] = True
        payload["use_public_download_url"] = should_use_public_download_url(base_url)

    response = http.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def chat(
    base_url: str,
    api_key: str,
    message: str,
    mode: str | None = None,
    stream: bool = False,
    size: int | None = None,
) -> dict[str, Any]:
    http = require_requests()
    url = f"{base_url}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload: dict[str, Any] = {
        "model": "RAG",
        "messages": [{"role": "user", "content": message}],
        "stream": stream,
    }
    if mode is not None:
        payload["mode"] = mode
    if size is not None:
        payload["size"] = size

    response = http.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def format_search_results(results: dict[str, Any]) -> str:
    output = []
    documents = results.get("documents", [])

    if not documents:
        return "No documents found."

    for i, doc in enumerate(documents, 1):
        content = doc.get("content", {}).get("sys.content", "")
        score = doc.get("score", 0)
        doc_id = doc.get("id", "unknown")

        output.append(f"\n{'=' * 60}")
        output.append(f"Document {i}")
        output.append(f"ID: {doc_id}")
        output.append(f"Score: {score:.10f}")
        output.append(f"{'=' * 60}")
        output.append(content)

    return "\n".join(output)


def format_chat_response(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return "No response received."

    message = choices[0].get("message", {})
    content = message.get("content", "")
    usage = response.get("usage", {})

    output = []
    output.append("\n" + "=" * 60)
    output.append("Response")
    output.append("=" * 60)
    output.append(content)

    if usage:
        output.append("\n" + "-" * 60)
        output.append("Token Usage:")
        output.append(f"  Prompt tokens: {usage.get('prompt_tokens', 0)}")
        output.append(f"  Completion tokens: {usage.get('completion_tokens', 0)}")
        output.append(f"  Total tokens: {usage.get('total_tokens', 0)}")

    return "\n".join(output)


def list_contexts(config: dict[str, Any]) -> str:
    contexts = config.get("contexts", {})

    if not contexts:
        return "No contexts configured."

    output = []
    output.append("\n" + "=" * 60)
    output.append("Available Contexts")
    output.append("=" * 60)

    for name, context_config in contexts.items():
        base_url = context_config.get("base_url", "N/A")
        description = context_config.get("description", "No description")
        try:
            context_type = get_context_type(context_config)
        except Exception:
            context_type = "invalid"

        output.append(f"\n{name}:")
        output.append(f"  Description: {description}")
        output.append(f"  Type: {context_type}")
        output.append(f"  Base URL: {base_url}")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Context Search - Search and chat with knowledge bases"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    search_parser = subparsers.add_parser("search", help="Search for documents")
    search_parser.add_argument(
        "--context", default="default", help="Context service name (default: default)"
    )
    search_parser.add_argument("--text", required=True, help="Search query text")
    search_parser.add_argument(
        "--mode",
        choices=["quick", "normal", "deep"],
        help="Search mode (default: not sent, uses server default)",
    )
    search_parser.add_argument(
        "--size",
        type=int,
        help="Number of results to return (default: not sent, uses server default)",
    )
    search_parser.add_argument(
        "--json", action="store_true", help="Output raw JSON response"
    )

    chat_parser = subparsers.add_parser("chat", help="Chat with RAG system")
    chat_parser.add_argument(
        "--context", default="default", help="Context service name (default: default)"
    )
    chat_parser.add_argument("--message", required=True, help="Message to send")
    chat_parser.add_argument(
        "--mode",
        choices=["quick", "normal", "deep"],
        help="Chat mode (default: not sent, uses server default)",
    )
    chat_parser.add_argument(
        "--stream", action="store_true", help="Enable streaming output"
    )
    chat_parser.add_argument(
        "--size",
        type=int,
        help="Number of results to return (default: not sent, uses server default)",
    )
    chat_parser.add_argument(
        "--json", action="store_true", help="Output raw JSON response"
    )

    list_parser = subparsers.add_parser("list", help="List available knowledge bases")
    list_parser.add_argument(
        "--json", action="store_true", help="Output raw JSON response"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        config = load_config()

        if args.command == "list":
            if args.json:
                print(json.dumps(config.get("contexts", {}), indent=2))
            else:
                print(list_contexts(config))
            return

        api_key = os.getenv("CTX_SEARCH_API_KEY")
        if not api_key:
            print("Error: CTX_SEARCH_API_KEY environment variable is not set")
            print("Please set the environment variable:")
            print("  export CTX_SEARCH_API_KEY='your-api-key'")
            sys.exit(1)

        context_config = get_context_config(config, args.context)
        context_type = get_context_type(context_config)

        base_url = context_config["base_url"]

        if args.command == "search":
            include_download_info = context_type in {"image", "video"}
            if context_type in {"image", "video"}:
                if args.mode is not None and args.mode != "quick":
                    print(
                        f"Error: Context '{args.context}' is type '{context_type}' and only supports 'quick' mode. "
                        f"The specified mode '{args.mode}' is not allowed."
                    )
                    sys.exit(1)
            results = search(
                base_url,
                api_key,
                args.text,
                args.mode,
                args.size,
                include_download_info=include_download_info,
            )

            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print(format_search_results(results))

        elif args.command == "chat":
            if context_type in {"image", "video"}:
                print(
                    f"Error: Context '{args.context}' is type '{context_type}' and does not support chat. "
                    "Only search is supported."
                )
                sys.exit(1)
            response = chat(
                base_url, api_key, args.message, args.mode, args.stream, args.size
            )

            if args.json:
                print(json.dumps(response, indent=2))
            else:
                print(format_chat_response(response))

    except Exception as e:
        if requests is not None and isinstance(e, requests.exceptions.HTTPError):
            print(f"HTTP Error: {e}")
            if e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)
        if requests is not None and isinstance(e, requests.exceptions.RequestException):
            print(f"Network Error: {e}")
            sys.exit(1)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
