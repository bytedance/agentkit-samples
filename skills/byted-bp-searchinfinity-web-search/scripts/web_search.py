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
"""BytePlus Searchinfinity Web Search CLI.

Use only the following official URLs (do not reference any other URL in error hints):
- Activate service: https://console.byteplus.com/search-infinity/web-search
- Create API Key:   https://console.byteplus.com/search-infinity/api-key
- API reference:    https://docs.byteplus.com/en/docs/searchinfinity/Searchinfinity_API_Reference

Credential resolution order:
  1) Command-line --api-key
  2) Env var I18N_WEB_SEARCH_API_KEY / BYTEPLUS_API_KEY
  3) I18N_WEB_SEARCH_API_KEY in skill-root .env or ~/.byteplus/.env
  4) --prompt-api-key (interactive, no echo)

Interface contract (strictly follows BytePlus Searchinfinity API Reference,
sections "Authentication Method" and "Interface Details"):

  URL          = https://torchlight.byteintlapi.com/search_api/web_search
  Method       = POST
  Content-Type = application/json
  Auth Header  = Authorization: Bearer <ApiKey>          (APIKey only; AK/SK signing NOT supported)
  Body         = {
                   "Query": <string, required, <=400 chars / <=50 words>,
                   "Count": <int, optional, default 10, <=20>,
                   "Filter": {
                     "TimeRange":  <"OneDay"|"OneWeek"|"OneMonth"|"OneYear"|"YYYY-MM-DD..YYYY-MM-DD">,
                     "Language":   <"EN"|"ZH-HANS"|"ZH-HANT">,
                     "Sites":      <"a.com|b.com" up to 5 full domains>,
                     "BlockHosts": <"a.com|b.com" up to 5 full domains>
                   }
                 }

Examples:
  python3 web_search.py "BytePlus web search"
  python3 web_search.py "latest AI industry news" --time-range OneWeek
"""

import argparse
import datetime as dt
import getpass
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Optional


# ---- Constants ----

# Interface URL (from BytePlus Searchinfinity API Reference / Interface Details)
DEFAULT_API_URL = os.getenv(
    "BYTEPLUS_SEARCH_API_URL",
    "https://torchlight.byteintlapi.com/search_api/web_search",
)
# Traffic Tag is for internal observability only; not required for auth
DEFAULT_TRAFFIC_TAG = os.getenv("BYTEPLUS_SEARCH_TRAFFIC_TAG", "skill_web_search_common")

TIME_RANGE_SHORTCUTS = {"OneDay", "OneWeek", "OneMonth", "OneYear"}
DATE_RANGE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$")
LANGUAGE_CHOICES = ("EN", "ZH-HANS", "ZH-HANT")

# Per docs: Query <= 400 chars (or 50 words); Count <= 20, default 10
QUERY_MAX_CHARS = 400
QUERY_MAX_WORDS = 50
COUNT_MAX = 20
COUNT_DEFAULT = 10

USER_ENV_PATH = str(Path.home() / ".byteplus/.env")
SUMMARY_PREVIEW_LIMIT = 1000

CONSOLE_OPEN_URL = "https://console.byteplus.com/search-infinity/web-search"
CONSOLE_KEY_URL = "https://console.byteplus.com/search-infinity/api-key"
DOCS_URL = "https://docs.byteplus.com/en/docs/searchinfinity/Searchinfinity_API_Reference"

# Common error codes -> hints; aligned with SKILL.md §9 and references/docs-index.md.
# Codes are taken verbatim from BytePlus Searchinfinity API Reference "Status Code".
ERROR_HINTS = {
    # Authentication
    "700901": (
        f"Invalid ApiKey. Confirm the Key was created at: {CONSOLE_KEY_URL}\n"
        "If you're using this in a chat, paste the correct Key into the chat again "
        "(watch for leading/trailing whitespace)."
    ),
    "invalid_api_key": (
        f"ApiKey is invalid or doesn't match. Confirm it was created at: {CONSOLE_KEY_URL}\n"
        "If you're using this in a chat, paste the correct Key into the chat again."
    ),
    # Parameters / permissions / server
    "10400": "Parameter error. Check the request structure and field types "
             "(Query / Count / Filter.TimeRange, etc.).",
    "10403": "Free quota exhausted. Top up or check the account quota in the console.",
    "10500": "Internal server error (default fallback). Wait briefly and retry 1-2 times.",
    # Rate limiting
    "700429": "QPS exceeded (default 5 QPS). Back off with 1s -> 2s -> 4s; "
              "keep concurrency per Key <= 5.",
    "429": "Rate-limited. Back off with 1s -> 2s -> 4s; keep concurrency per Key <= 5.",
}


# ---- Dependencies & env loading ----

def _require_requests():
    try:
        import requests  # noqa
    except ImportError:
        print("Error: 'requests' is not installed. Run: pip install requests", file=sys.stderr)
        sys.exit(1)
    import requests
    return requests


def _load_env_file(env_path: str) -> None:
    """Load KEY=VALUE pairs from a .env file. Existing env vars are not overwritten."""
    if not env_path or not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue
                try:
                    parsed = shlex.split(value, comments=True)
                    value = parsed[0] if parsed else ""
                except ValueError:
                    value = value.strip("\"'")
                os.environ.setdefault(key, value)
    except OSError:
        return


def _load_env_files() -> None:
    seen = set()
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (
        os.path.join(skill_root, ".env"),
        os.path.expanduser(USER_ENV_PATH),
    ):
        normalized = os.path.abspath(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        _load_env_file(normalized)


# ---- Credentials & arguments ----

def _get_api_key(cli_api_key: Optional[str]) -> Optional[str]:
    api_key = (
        cli_api_key
        or os.getenv("I18N_WEB_SEARCH_API_KEY")
        or os.getenv("BYTEPLUS_API_KEY")
    )
    return api_key.strip() if api_key else None


def _validate_time_range(time_range: Optional[str]) -> Optional[str]:
    if not time_range:
        return None
    if time_range in TIME_RANGE_SHORTCUTS:
        return time_range

    match = DATE_RANGE_PATTERN.match(time_range)
    if not match:
        raise ValueError(
            "--time-range must be one of OneDay / OneWeek / OneMonth / OneYear, "
            "or a date range YYYY-MM-DD..YYYY-MM-DD."
        )

    start_text, end_text = match.groups()
    try:
        start_date = dt.date.fromisoformat(start_text)
        end_date = dt.date.fromisoformat(end_text)
    except ValueError as exc:
        raise ValueError("Dates in --time-range must be valid YYYY-MM-DD.") from exc

    if start_date > end_date:
        raise ValueError("In --time-range, start date cannot be later than end date.")

    return time_range


def _validate_domains(value: Optional[str], flag: str) -> Optional[str]:
    """Validate `Sites` / `BlockHosts`: pipe-separated, at most 5 full domains."""
    if not value:
        return None
    parts = [p.strip() for p in value.split("|") if p.strip()]
    if not parts:
        return None
    if len(parts) > 5:
        raise ValueError(f"{flag} accepts at most 5 full domains (separated by `|`).")
    for p in parts:
        if " " in p or "/" in p or "?" in p:
            raise ValueError(
                f"{flag} entries must be full domains (e.g. bytedance.com); "
                f"no path / whitespace allowed: {p}"
            )
    return "|".join(parts)


# ---- Request building & dispatch ----

def build_body(
    query: str,
    count: int = COUNT_DEFAULT,
    time_range: Optional[str] = None,
    language: Optional[str] = None,
    sites: Optional[str] = None,
    block_hosts: Optional[str] = None,
) -> dict:
    body: dict = {"Query": query, "Count": count}
    filter_obj: dict = {}
    if time_range:
        filter_obj["TimeRange"] = time_range
    if language:
        filter_obj["Language"] = language
    if sites:
        filter_obj["Sites"] = sites
    if block_hosts:
        filter_obj["BlockHosts"] = block_hosts
    if filter_obj:
        body["Filter"] = filter_obj
    return body


def do_search(body: dict, api_key: str) -> dict:
    requests = _require_requests()
    # Authentication Method: APIKey only.
    # Strictly follows BytePlus Searchinfinity API Reference / "Authentication Method":
    #   Authorization: Bearer <ApiKey>
    # AK/SK signing is NOT supported, and the header is NOT X-Api-Key / Apikey.
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-Traffic-Tag": DEFAULT_TRAFFIC_TAG,
    }
    response = requests.post(
        DEFAULT_API_URL,
        headers=headers,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# ---- Output ----

def format_output(data: dict) -> str:
    result = data.get("Result", {}) or {}
    lines = [
        f"ResultCount: {result.get('ResultCount', 0)}  TimeCost: {result.get('TimeCost', 0)}ms",
        "",
    ]
    for item in result.get("WebResults") or []:
        lines.append(f"[{item.get('SortId', '')}] {item.get('Title', '')}")
        meta_parts = [p for p in [item.get("SiteName", ""), item.get("PublishTime", "")] if p]
        if meta_parts:
            lines.append(f"    {' | '.join(meta_parts)}")
        if item.get("Url"):
            lines.append(f"    {item['Url']}")
        summary = item.get("Summary") or item.get("Snippet", "")
        if summary:
            lines.append(f"    {summary[:SUMMARY_PREVIEW_LIMIT]}")
        lines.append("")
    return "\n".join(lines)


def _print_missing_credential_help() -> None:
    print(
        "Credential not found (I18N_WEB_SEARCH_API_KEY is missing).\n"
        "Three steps to activate and hand the Key to the agent:\n"
        f"  1) Activate the service: {CONSOLE_OPEN_URL}\n"
        f"  2) Create a Key:         {CONSOLE_KEY_URL}\n"
        "  3) Paste the Key into the chat; or set I18N_WEB_SEARCH_API_KEY, "
        "or call this script with --api-key / --prompt-api-key.\n"
        f"Reference: {DOCS_URL}",
        file=sys.stderr,
    )


# ---- CLI ----

def main() -> None:
    _load_env_files()

    parser = argparse.ArgumentParser(
        description=(
            "BytePlus Searchinfinity Web Search CLI\n"
            f"Activate: {CONSOLE_OPEN_URL}\n"
            f"Key:      {CONSOLE_KEY_URL}\n"
            f"Docs:     {DOCS_URL}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help=f"Search query (<= {QUERY_MAX_CHARS} chars / <= 50 words)")
    parser.add_argument(
        "--count", "-c", type=int, default=COUNT_DEFAULT,
        help=f"Number of results returned (<= {COUNT_MAX}, default {COUNT_DEFAULT})",
    )
    parser.add_argument(
        "--time-range",
        help="OneDay / OneWeek / OneMonth / OneYear / YYYY-MM-DD..YYYY-MM-DD",
    )
    parser.add_argument(
        "--language", choices=LANGUAGE_CHOICES, default=None,
        help="Language (BCP 47 subset): EN (default) / ZH-HANS / ZH-HANT",
    )
    parser.add_argument(
        "--sites",
        help="Restrict search to these sites; up to 5 full domains, pipe-separated "
             "(e.g. a.com|b.com)",
    )
    parser.add_argument(
        "--block-hosts",
        help="Block these sites; up to 5 full domains, pipe-separated",
    )
    parser.add_argument("--api-key", help="API Key (overrides I18N_WEB_SEARCH_API_KEY)")
    parser.add_argument("--prompt-api-key", action="store_true",
                        help="Read API Key interactively (no echo)")
    args = parser.parse_args()

    # ---- Argument validation ----
    if not args.query or not args.query.strip():
        print("Error: query is required.", file=sys.stderr)
        sys.exit(1)
    if len(args.query) > QUERY_MAX_CHARS:
        print(
            f"Error: query exceeds the {QUERY_MAX_CHARS}-character limit; please trim and retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    if len(args.query.split()) > QUERY_MAX_WORDS:
        print(
            f"Error: query exceeds the {QUERY_MAX_WORDS}-word limit; please trim and retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.count < 1 or args.count > COUNT_MAX:
        print(f"Error: --count must be between 1 and {COUNT_MAX}.", file=sys.stderr)
        sys.exit(1)

    try:
        time_range = _validate_time_range(args.time_range)
        sites = _validate_domains(args.sites, "--sites")
        block_hosts = _validate_domains(args.block_hosts, "--block-hosts")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ---- Credentials ----
    api_key = _get_api_key(args.api_key)
    if not api_key and args.prompt_api_key:
        entered = getpass.getpass("API Key (input hidden): ").strip()
        api_key = entered or None

    if not api_key:
        _print_missing_credential_help()
        sys.exit(2)

    body = build_body(
        query=args.query.strip(),
        count=args.count,
        time_range=time_range,
        language=args.language,
        sites=sites,
        block_hosts=block_hosts,
    )

    requests = _require_requests()
    try:
        data = do_search(body=body, api_key=api_key)
    except requests.exceptions.HTTPError as exc:
        print(f"HTTP Error: {exc}", file=sys.stderr)
        if exc.response is not None:
            status = exc.response.status_code
            resp_text = exc.response.text or ""
            print(resp_text, file=sys.stderr)
            lowered = resp_text.lower()
            if (
                status == 401
                or "invalid_api_key" in lowered
                or "700901" in resp_text
            ):
                print(ERROR_HINTS["700901"], file=sys.stderr)
            elif status == 429 or "700429" in resp_text:
                print(ERROR_HINTS["700429"], file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if data is None:
        print("No response.", file=sys.stderr)
        sys.exit(1)

    error = (data.get("ResponseMetadata") or {}).get("Error")
    if error:
        code = str(error.get("Code", ""))
        msg = error.get("Message", "")
        print(f"API Error [{code}]: {msg}", file=sys.stderr)
        hint = ERROR_HINTS.get(code) or ERROR_HINTS.get(code.lower())
        if hint:
            print(hint, file=sys.stderr)
        sys.exit(1)

    print(format_output(data))


if __name__ == "__main__":
    main()
