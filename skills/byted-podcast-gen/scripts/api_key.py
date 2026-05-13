import json
import os
import urllib.error
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def _build_action_url(base: str, action: str, version: str = "2025-05-20") -> str:
    base = (base or "").strip()
    if not base:
        return ""
    parsed = urlparse(base)
    path = parsed.path or "/"
    if not path.endswith("/"):
        path = f"{path}/"
    query = dict(parse_qsl(parsed.query))
    query["Action"] = action
    query["Version"] = version
    return urlunparse(parsed._replace(path=path, query=urlencode(query)))


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def _post_json(
    url: str, headers: dict, payload: dict, timeout_s: int = 15
) -> dict | None:
    if not url:
        return None
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in (headers or {}).items():
        if v is None:
            continue
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return _extract_json(body)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
            return _extract_json(body)
        except Exception:
            return None
    except Exception:
        return None


def _dotenv_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _load_dotenv_if_available(dotenv_path: str) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    try:
        load_dotenv(dotenv_path=dotenv_path, override=False)
    except Exception:
        return


def _persist_env_to_dotenv_if_available(dotenv_path: str, key: str, value: str) -> None:
    value = (value or "").strip()
    if not value:
        return
    try:
        from dotenv import set_key  # type: ignore
    except Exception:
        return
    try:
        os.makedirs(os.path.dirname(dotenv_path) or ".", exist_ok=True)
        set_key(dotenv_path, key, value, quote_mode="never")
        try:
            os.chmod(dotenv_path, 0o600)
        except Exception:
            pass
    except Exception:
        return


def get_speech_api_key(
    project_name: str = "default", create_name: str = "arkclaw"
) -> str:
    _load_dotenv_if_available(_dotenv_path())

    speech_key = os.getenv("MODEL_SPEECH_API_KEY", "").strip()
    if speech_key:
        return speech_key

    ark_key = os.getenv("ARK_SKILL_API_KEY", "").strip()
    base = os.getenv("ARK_SKILL_API_BASE", "").strip()
    if not ark_key or not base:
        return ""

    headers = {
        "ServiceName": "speech_saas_prod",
        "Authorization": f"Bearer {ark_key}",
        "Content-Type": "application/json",
    }

    list_url = _build_action_url(base, "ListAPIKeys")
    list_data = _post_json(
        list_url,
        headers=headers,
        payload={"ProjectName": project_name, "OnlyAvailable": True},
    )
    if isinstance(list_data, dict):
        api_keys = (list_data.get("Result") or {}).get("APIKeys") or []
        if isinstance(api_keys, list) and api_keys:
            first = api_keys[0] if isinstance(api_keys[0], dict) else {}
            first_key = (first.get("APIKey") or "").strip()
            if first_key:
                os.environ["MODEL_SPEECH_API_KEY"] = first_key
                _persist_env_to_dotenv_if_available(
                    _dotenv_path(), "MODEL_SPEECH_API_KEY", first_key
                )
                return first_key

    create_url = _build_action_url(base, "CreateAPIKey")
    create_data = _post_json(
        create_url,
        headers=headers,
        payload={"ProjectName": project_name, "Name": create_name},
    )
    if isinstance(create_data, dict):
        created_key = ((create_data.get("Result") or {}).get("APIKey") or "").strip()
        if created_key:
            os.environ["MODEL_SPEECH_API_KEY"] = created_key
            _persist_env_to_dotenv_if_available(
                _dotenv_path(), "MODEL_SPEECH_API_KEY", created_key
            )
            return created_key

    return ""
