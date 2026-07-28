#!/usr/bin/env python3
import datetime
import hashlib
import hmac
import json
import os
from urllib.parse import quote

REQUIRED_CONFIG_KEYS = (
    "volcengine_access_key",
    "volcengine_secret_key",
    "volcengine_region",
    "volcengine_agentkit_host",
    "volcengine_agentkit_api_version",
    "volcengine_agentkit_service",
)


def config_value(config, key):
    value = config.get(key)
    if isinstance(value, str):
        return value.strip()
    return value


def to_pascal_case(snake_str: str) -> str:
    return "".join(word.capitalize() for word in snake_str.split("_"))


def _build_get_query_params(body: dict) -> dict:
    params = {}
    for key, value in body.items():
        pascal_key = to_pascal_case(key)
        if isinstance(value, list):
            for idx, item in enumerate(value, start=1):
                params[f"{pascal_key}.{idx}"] = item
        else:
            params[pascal_key] = value
    return params


def _redact_headers(headers):
    redacted = {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


def write_api_log(log_path, record):
    if not log_path:
        return

    directory = os.path.dirname(os.path.abspath(log_path))
    os.makedirs(directory, exist_ok=True)
    with open(log_path, "a") as f:
        json.dump(record, f, indent=2, ensure_ascii=False, default=str)
        f.write("\n")


def load_config(config_path: str):
    if not config_path:
        raise ValueError("Missing required config_path; pass --config PATH")

    with open(config_path, "r") as f:
        config = json.load(f)

    missing = [key for key in REQUIRED_CONFIG_KEYS if not config_value(config, key)]
    if missing:
        raise ValueError(
            f"Missing required config field(s) in {config_path}: {', '.join(sorted(missing))}"
        )
    return config


def hmac_sha256(key, msg):
    if isinstance(key, str):
        key = key.encode("utf-8")
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def get_signing_key(sk, date, region, service):
    k_date = hmac_sha256(sk, date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, service)
    return hmac_sha256(k_service, "request")


def sign_request(method, host, path, query, headers, body, ak, sk, region, service):
    format_date = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    headers["X-Date"] = format_date
    headers["Host"] = host

    if isinstance(body, bytes):
        body_hash = hashlib.sha256(body).hexdigest()
    else:
        if isinstance(body, str):
            body_str = body
        elif body is None:
            body_str = ""
        else:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
    headers["X-Content-Sha256"] = body_hash

    signed_headers = {}
    for key in headers:
        lower_key = key.lower()
        if lower_key in ("content-type", "host") or lower_key.startswith("x-"):
            signed_headers[lower_key] = headers[key]

    if "host" in signed_headers and ":" in signed_headers["host"]:
        host_parts = signed_headers["host"].split(":")
        if host_parts[1] in ("80", "443"):
            signed_headers["host"] = host_parts[0]

    signed_str = ""
    for key in sorted(signed_headers.keys()):
        signed_str += key + ":" + signed_headers[key] + "\n"

    signed_headers_string = ";".join(sorted(signed_headers.keys()))
    canonical_query = "&".join(
        f"{quote(k, safe='-_.~')}={quote(str(v), safe='-_.~')}"
        for k, v in sorted(query.items())
    )
    canonical_request = "\n".join(
        [
            method,
            path,
            canonical_query,
            signed_str,
            signed_headers_string,
            body_hash,
        ]
    )

    credential_scope = "/".join([format_date[:8], region, service, "request"])
    signing_str = "\n".join(
        [
            "HMAC-SHA256",
            format_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    signing_key = get_signing_key(sk, format_date[:8], region, service)
    signature = hmac.new(
        signing_key, signing_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    credential = ak + "/" + credential_scope
    headers["Authorization"] = (
        f"HMAC-SHA256 Credential={credential}, "
        f"SignedHeaders={signed_headers_string}, Signature={signature}"
    )
    return headers


def call_api(
    action,
    body=None,
    host=None,
    region=None,
    service=None,
    api_version=None,
    method="POST",
    verbose=True,
    config_path=None,
    log_path=None,
):
    config = load_config(config_path)

    ak = config["volcengine_access_key"]
    sk = config["volcengine_secret_key"]

    region = region or config["volcengine_region"]
    host = host or config["volcengine_agentkit_host"]
    api_version = api_version or config["volcengine_agentkit_api_version"]
    service = service or config["volcengine_agentkit_service"]
    x_forward_env = config.get("x_forward_env")

    path = "/"
    body = {} if body is None else body
    query = {
        "Action": action,
        "Version": api_version,
    }

    method = method.upper()
    if method == "GET":
        query.update(_build_get_query_params(body))
        sign_body = ""
        body_bytes = None
        headers = {}
    else:
        sign_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        body_bytes = sign_body.encode("utf-8")
        headers = {"Content-Type": "application/json"}

    if x_forward_env:
        headers["X-Forward-Env"] = x_forward_env

    headers = sign_request(
        method, host, path, query, headers, sign_body, ak, sk, region, service
    )
    query_string = "&".join(
        f"{quote(str(k), safe='-_.~')}={quote(str(v), safe='-_.~')}"
        for k, v in query.items()
    )
    url = f"https://{host}{path}?{query_string}"

    log_record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "request": {
            "method": method,
            "url": url,
            "host": host,
            "region": region,
            "service": service,
            "version": api_version,
            "headers": _redact_headers(headers),
            "body": body,
        },
    }

    import requests

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=30)
        else:
            resp = requests.post(url, headers=headers, data=body_bytes, timeout=30)
    except Exception as exc:
        log_record["response"] = {
            "error": str(exc),
        }
        write_api_log(log_path, log_record)
        raise

    try:
        result = resp.json()
    except ValueError:
        result = {
            "ResponseMetadata": {
                "Error": {"Code": "NonJsonResponse", "Message": resp.text}
            }
        }

    log_record["response"] = {
        "http_status": resp.status_code,
        "body": result,
    }

    metadata = result.get("ResponseMetadata", {})
    error = metadata.get("Error")
    log_record["summary"] = {
        "success": not bool(error),
        "request_id": metadata.get("RequestId"),
        "error": error,
    }
    write_api_log(log_path, log_record)

    return result
