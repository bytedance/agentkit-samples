"""火山引擎/BytePlus CP 生产环境 OpenAPI 客户端（Signature V4）。

仅连接固定白名单中的生产 endpoint；不接受 endpoint、签名 region 或 service 的环境变量覆盖。
签名细节参考 https://www.volcengine.com/docs/6461/1277764 。
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

VERSION = "2023-05-01"
SERVICE = "cp"

# 流水线运行实例（PipelineRun）/ stage / task 的状态枚举。
# 服务端不同模块用词不一致：PipelineRun 用 Running，stage/task 可能返回 InProgress，
# 二者语义都是“运行中”；取消中 PipelineRun 可能长期返回 Canceling，但业务上已代表
# 取消请求生效，按 Canceled 处理。轮询时用 normalize_status 归一化，避免漏判。
RUN_STATUSES = [
    "Enqueued", "Dequeued", "LockWaiting", "Queued", "Running", "InProgress",
    "Canceling", "Canceled", "Timeout", "Failed", "Succeeded",
]
# 别名 -> 规范状态。把 InProgress 归一到 Running，Canceling 归一到 Canceled，
# 方便上层判断是否仍在执行 / 是否已取消。
_STATUS_ALIASES = {"InProgress": "Running", "Canceling": "Canceled"}
# 已结束（终态）的状态集合。
TERMINAL_STATUSES = {"Canceled", "Timeout", "Failed", "Succeeded"}

# CP 对象 ID 通常是 32 位 hex。自然语言引用可带 prod 前缀，但明确的 pre 引用必须拒绝，
# 避免把预发对象误当作生产目标。
_OBJECT_ID_RE = re.compile(r"(?i)(?:prod)?([0-9a-f]{32})")
_PRE_WORKSPACE_REF_RE = re.compile(
    r"(?i)(?:cp_pre|(?:北京|柔佛|johor|ap-southeast-1)?\s*pre\s*[-_:]?\s*"
    r"(?=[0-9a-f]{32}))"
)
_SECRET_PATTERNS = [
    re.compile(r"(?i)(AccessKeyID\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(SecretAccessKey\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(CP_ACCESS_KEY\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(CP_SECRET_KEY\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(VOLC_ACCESSKEY\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(VOLC_SECRETKEY\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(BYTEPLUS_ACCESSKEY\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(BYTEPLUS_SECRETKEY\s*=\s*[\"']?)([^\"'\s,]+)"),
    re.compile(r"(?i)(Authorization\s*:\s*)(?:Bearer\s+)?([^\s,]+)"),
    re.compile(
        r"(?i)((?:authorization|access[_-]?key(?:id)?|secret[_-]?(?:access[_-]?)?key|"
        r"[a-z0-9_-]*(?:token|secret|password|passwd|cookie|private[_-]?key|"
        r"credentials?)[a-z0-9_-]*|kubeconfig|webhookurl|downloadurl|loguri)"
        r"\s*[:=]\s*[\"']?)([^\"'\s,}]+)"
    ),
    re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9._~+/-]+=*)"),
    re.compile(
        r"(?s)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----).*?"
        r"(-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    ),
]

_SENSITIVE_KEY_RE = re.compile(
    r"(?i)^(?:accesskey(?:id)?|secretaccesskey|cpaccesskey|cpsecretkey|"
    r"volcaccesskey|volcsecretkey|byteplusaccesskey|byteplussecretkey|"
    r"[a-z0-9]*(?:authorization|token|secret(?:key)?|password|passwd|cookie|"
    r"privatekey|credentials?)[a-z0-9]*|kubeconfig|componentstepyaml|"
    r"webhookurl|downloadurl|loguri|url|yaml|script)$"
)
_SENSITIVE_JSON_VALUE_RE = re.compile(
    r"(?i)([\"']?(?:authorization|access[_-]?key(?:id)?|"
    r"secret[_-]?(?:access[_-]?)?key|[a-z0-9_-]*(?:token|secret|password|passwd|"
    r"cookie|private[_-]?key|credentials?)[a-z0-9_-]*|kubeconfig|webhookurl|"
    r"downloadurl|loguri)[\"']?\s*:\s*[\"'])"
    r"([^\"']+)([\"'])"
)


def normalize_status(status: Optional[str]) -> str:
    """把服务端返回的状态归一化（如 InProgress -> Running）。"""
    if not status:
        return ""
    return _STATUS_ALIASES.get(status, status)


def is_terminal_status(status: Optional[str]) -> bool:
    """状态是否为终态（不会再变化）。"""
    return normalize_status(status) in TERMINAL_STATUSES


def redact_secret(text: str) -> str:
    """脱敏 AK/SK 等敏感信息，避免把凭证打印到日志 / 文档。"""
    redacted = _SENSITIVE_JSON_VALUE_RE.sub(r"\1<redacted>\3", text)
    for pattern in _SECRET_PATTERNS:
        if "PRIVATE KEY" in pattern.pattern:
            redacted = pattern.sub(r"\1<redacted>\2", redacted)
        else:
            redacted = pattern.sub(r"\1<redacted>", redacted)
    return redacted


def redact_value(value: Any, key: Optional[str] = None) -> Any:
    """Recursively redact credential-like values while preserving response shape."""
    if key and _SENSITIVE_KEY_RE.match(re.sub(r"[^A-Za-z0-9]", "", key)):
        return "<redacted>"
    if isinstance(value, dict):
        return {k: redact_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        # Config fields in CP responses are sometimes JSON encoded strings. Redact their
        # leaves too, but keep the field a string so callers observe the same type.
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(parsed, (dict, list)):
                    return json.dumps(redact_value(parsed), ensure_ascii=False)
        return redact_secret(value)
    return value


def load_json_object(
    file_path: Optional[str] = None, inline_json: Optional[str] = None
) -> Dict[str, Any]:
    """Load exactly one JSON object from a file or inline argument."""
    if bool(file_path) == bool(inline_json):
        raise SystemExit("必须且只能提供 --body-file 或 --body-json 其中一个")
    try:
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                value = json.load(f)
        else:
            value = json.loads(inline_json or "")
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON 请求体: {redact_secret(str(exc))}") from exc
    if not isinstance(value, dict):
        raise SystemExit("--body-file/--body-json 必须包含一个 JSON object")
    return value


def merge_target_identifiers(
    payload: Dict[str, Any], workspace_id: str, app_id: Optional[str] = None
) -> Dict[str, Any]:
    """Copy a payload and inject explicit targets, rejecting conflicting values."""
    body = copy.deepcopy(payload)
    targets = {"WorkspaceId": workspace_id}
    if app_id is not None:
        targets["AppId"] = app_id
    for field, expected in targets.items():
        actual = body.get(field)
        if actual is not None and actual != expected:
            raise SystemExit(
                f"JSON 请求体中的 {field} 与命令行目标不一致；"
                f"请删除该字段或改为显式目标 {expected}"
            )
        body[field] = expected
    return body


def merge_explicit_fields(payload: Dict[str, Any], **fields: Any) -> Dict[str, Any]:
    """Copy a JSON payload and merge explicit CLI fields without target ambiguity."""
    body = copy.deepcopy(payload)
    for field, expected in fields.items():
        if expected is None:
            continue
        actual = body.get(field)
        if actual is not None and actual != expected:
            raise SystemExit(
                f"JSON 请求体中的 {field} 与命令行目标不一致；"
                f"请删除该字段或改为显式目标 {expected}"
            )
        body[field] = expected
    return body


def extract_result(response: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Return a normalized Result object and ResponseMetadata.RequestId."""
    result = response.get("Result") or {}
    if not isinstance(result, dict):
        result = {"Value": result}
    metadata = response.get("ResponseMetadata") or {}
    request_id = metadata.get("RequestId") if isinstance(metadata, dict) else None
    return result, request_id


def paginate_numbered(
    c: "CPClient",
    action: str,
    base_body: Dict[str, Any],
    page_size: int = 100,
    max_results: Optional[int] = None,
    total_keys: Tuple[str, ...] = ("TotalCount", "Total"),
    request_ids: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Page any PageNumber/PageSize API without mutating the supplied body."""
    if page_size < 1 or page_size > 100:
        raise SystemExit("page_size 必须在 1~100 之间")
    if max_results is not None and max_results < 1:
        raise SystemExit("max_results 必须大于 0，或使用 None 获取全部记录")

    items: List[Dict[str, Any]] = []
    page = 1
    total = 0
    while True:
        body = copy.deepcopy(base_body)
        body["PageNumber"] = page
        body["PageSize"] = page_size
        response = c.call(action, body)
        result, request_id = extract_result(response)
        if request_ids is not None and request_id:
            request_ids.append(request_id)
        batch = result.get("Items") or []
        total_value = next(
            (result.get(key) for key in total_keys if result.get(key) is not None),
            len(items) + len(batch),
        )
        total = int(total_value or 0)
        items.extend(batch)
        if max_results is not None and len(items) >= max_results:
            return items[:max_results], total
        if not batch or len(items) >= total:
            return items, total
        page += 1


def write_private_text(path: str, text: str) -> None:
    """Write sensitive text to a regular file with mode 0600 and no symlink follow."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise SystemExit(f"无法安全写入敏感输出文件 {path!r}: {exc}") from exc
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            stream.write(text)
    finally:
        if fd >= 0:
            os.close(fd)


# 当前 skill 仅放开生产环境，并固定两个公开地域：北京 / 柔佛。
# region 进入签名 CredentialScope，错填会被签名校验拒绝。
# agent_pool 为该地域公共构建集群在流水线 spec 里的 agentPool 取值（含 public/ 前缀）。
TARGETS: Dict[str, Dict[str, str]] = {
    "cn-beijing": {
        "endpoint": "cp.cn-beijing.volcengineapi.com",
        "region": "cn-beijing",
        "service": SERVICE,
        "agent_pool": "public/prod-v2-public",
        "provider": "volcengine",
    },
    "ap-southeast-1": {
        "endpoint": "cp.ap-southeast-1.byteplusapi.com",
        "region": "ap-southeast-1",
        "service": SERVICE,
        "agent_pool": "public/prod-v2-public",
        "provider": "byteplus",
    },
}

# CLI 和环境变量优先使用公开 Region ID；保留无环境语义的常见地域别名。
REGION_ALIASES: Dict[str, str] = {
    "bj": "cn-beijing",
    "cn-beijing": "cn-beijing",
    "beijing": "cn-beijing",
    "johor": "ap-southeast-1",
    "ap-southeast-1": "ap-southeast-1",
}


def resolve_region(region: Optional[str]) -> str:
    """把用户传入的地域名/别名/环境变量解析成 TARGETS 的 key。"""
    raw = region or os.environ.get("CP_REGION") or "cn-beijing"
    key = REGION_ALIASES.get(raw.strip().lower())
    if key is None:
        raise SystemExit(
            "byted-volcengine-cp 仅支持生产地域 "
            f"cn-beijing / ap-southeast-1，收到 region={raw!r}"
        )
    return key


def normalize_workspace_ref(raw: str, region: Optional[str] = None) -> Tuple[str, str]:
    """把自然语言工作区引用归一成 (workspace_id, region)。

    支持：
    - "北京prod<32hex>工作区" -> ("<32hex>", "cn-beijing")
    - "柔佛prod<32hex>" -> ("<32hex>", "ap-southeast-1")
    - "prod<32hex>" / "<32hex>" -> 使用传入 region 或默认 cn-beijing
    """
    if not raw:
        raise SystemExit("workspace id 不能为空")
    text = raw.strip()
    if _PRE_WORKSPACE_REF_RE.search(text):
        raise SystemExit("检测到 pre 工作区引用；本 skill 仅允许操作生产环境")
    inferred_region = region
    if "北京" in text:
        inferred_region = "cn-beijing"
    elif "柔佛" in text or "johor" in text.lower() or "ap-southeast-1" in text.lower():
        inferred_region = "ap-southeast-1"

    m = _OBJECT_ID_RE.search(text)
    if not m:
        raise SystemExit(
            f"无法从 workspace 引用中解析 32 位 hex ID: {redact_secret(text)!r}"
        )
    return m.group(1).lower(), resolve_region(inferred_region)


def agent_pool_for(region: Optional[str]) -> str:
    """返回该地域公共构建集群在 spec 里的 agentPool 取值。"""
    return TARGETS[resolve_region(region)]["agent_pool"]


# 匹配 spec YAML 里的 `agentPool: <value>` 行（保留缩进与可选引号 / 行尾注释）。
_AGENT_POOL_LINE = re.compile(
    r'^(?P<indent>\s*agentPool:\s*)'
    r'(?P<quote>["\']?)(?P<value>[^"\'#\s]+)(?P=quote)'
    r'(?P<trailing>\s*(?:#.*)?)$'
)


def rewrite_agent_pool(spec: str, region: Optional[str]) -> Tuple[str, List[Dict[str, str]]]:
    """把 spec 中所有 `agentPool:` 公共池行改写成目标地域的取值。

    仅改写 `public/` 公共池为生产公共池，`private/<自定义>` 私有池原样保留，
    避免误改用户专属构建集群。返回 (新 spec, 改写记录列表)。
    """
    target = agent_pool_for(region)
    changes: List[Dict[str, str]] = []

    def _sub(m: "re.Match[str]") -> str:
        value = m.group("value")
        if not value.startswith("public/") or value == target:
            return m.group(0)
        changes.append({"from": value, "to": target})
        return f'{m.group("indent")}{m.group("quote")}{target}{m.group("quote")}{m.group("trailing")}'

    new_spec = "\n".join(_AGENT_POOL_LINE.sub(_sub, line) for line in spec.split("\n"))
    return new_spec, changes


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _derive_signing_key(secret: str, short_date: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(secret.encode("utf-8"), short_date)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "request")


def _canonical_query(params: Dict[str, str]) -> str:
    items = []
    for k in sorted(params.keys()):
        items.append(
            urllib.parse.quote(k, safe="-_.~")
            + "="
            + urllib.parse.quote(params[k], safe="-_.~")
        )
    return "&".join(items)


def _build_ssl_context() -> ssl.SSLContext:
    """构造 HTTPS 验证用的 SSL context，缓解 macOS/Python 自带证书链不全的问题。

    优先级：
    1. 环境变量 SSL_CERT_FILE / SSL_CERT_DIR（标准 OpenSSL 约定）。
    2. 已安装的 certifi CA bundle（pip install certifi）。
    3. 系统默认（ssl.create_default_context）。

    生产 Skill 不提供跳过 TLS 校验的开关。
    """
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return ssl.create_default_context()
    try:
        import certifi  # noqa: PLC0415

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


_SSL_CONTEXT = _build_ssl_context()


class CPClient:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        service: str,
        region: str = "cn-beijing",
    ):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.service = service
        self.region = region

    def call(self, action: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body_bytes = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
        now = _dt.datetime.now(_dt.timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = now.strftime("%Y%m%d")

        query_params = {"Action": action, "Version": VERSION}
        canonical_query = _canonical_query(query_params)

        body_hash = _sha256_hex(body_bytes)
        host = self.endpoint
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_headers = (
            "content-type:application/json\n"
            f"host:{host}\n"
            f"x-content-sha256:{body_hash}\n"
            f"x-date:{x_date}\n"
        )
        canonical_request = "\n".join([
            "POST",
            "/",
            canonical_query,
            canonical_headers,
            signed_headers,
            body_hash,
        ])
        credential_scope = f"{short_date}/{self.region}/{self.service}/request"
        string_to_sign = "\n".join([
            "HMAC-SHA256",
            x_date,
            credential_scope,
            _sha256_hex(canonical_request.encode("utf-8")),
        ])
        signing_key = _derive_signing_key(
            self.secret_key, short_date, self.region, self.service
        )
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        authorization = (
            f"HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        url = f"https://{host}/?{canonical_query}"
        req = urllib.request.Request(url, data=body_bytes, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Host", host)
        req.add_header("X-Date", x_date)
        req.add_header("X-Content-Sha256", body_hash)
        req.add_header("Authorization", authorization)

        try:
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
                payload = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            status = exc.code
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
                raise RuntimeError(
                    redact_secret(
                        f"{action} TLS 证书校验失败：{reason}\n"
                        "macOS/Python 常见问题，可任选其一修复：\n"
                        "  1) pip3 install certifi          # 本 skill 会自动使用 certifi CA\n"
                        "  2) export SSL_CERT_FILE=$(python3 -m certifi)\n"
                        "  3) 运行 /Applications/Python\\ 3.x/Install\\ Certificates.command"
                    )
                ) from exc
            raise RuntimeError(redact_secret(f"{action} 网络错误：{reason}")) from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            raise RuntimeError(
                redact_secret(f"non-JSON response (status={status}): {payload[:500]}")
            )

        meta = data.get("ResponseMetadata", {})
        err = meta.get("Error") or data.get("Error")
        if err:
            raise RuntimeError(
                redact_secret(
                    f"{action} failed: code={err.get('Code')} "
                    f"message={err.get('Message')}"
                )
            )
        if status >= 300:
            raise RuntimeError(redact_secret(f"{action} http {status}: {payload[:500]}"))
        return data


def _validated_credentials(
    access_key: Optional[str],
    secret_key: Optional[str],
    pair_label: str,
) -> Optional[Tuple[str, str]]:
    """校验一组直接读取的环境凭证，避免把敏感变量名作为数据保存。"""
    if bool(access_key) != bool(secret_key):
        raise SystemExit(f"{pair_label} 必须成对设置")
    if access_key and secret_key:
        return access_key, secret_key
    return None


def _resolve_credentials(region: str) -> Tuple[str, str]:
    """从 CP 专用变量或地域对应云厂商的标准变量读取一组完整凭证。"""
    if region == "cn-beijing":
        provider_credentials = _validated_credentials(
            os.environ.get("VOLC_ACCESSKEY"),
            os.environ.get("VOLC_SECRETKEY"),
            "VOLC_ACCESSKEY / VOLC_SECRETKEY",
        )
    else:
        provider_credentials = _validated_credentials(
            os.environ.get("BYTEPLUS_ACCESSKEY"),
            os.environ.get("BYTEPLUS_SECRETKEY"),
            "BYTEPLUS_ACCESSKEY / BYTEPLUS_SECRETKEY",
        )
    cp_credentials = _validated_credentials(
        os.environ.get("CP_ACCESS_KEY"),
        os.environ.get("CP_SECRET_KEY"),
        "CP_ACCESS_KEY / CP_SECRET_KEY",
    )
    if provider_credentials and cp_credentials:
        raise SystemExit("检测到地域标准凭证与 CP 专用凭证；请只保留一组，避免账号歧义")
    resolved = provider_credentials or cp_credentials
    if resolved is None:
        raise SystemExit("缺少生产访问凭证；请设置地域标准 AK/SK 或 CP 专用 AK/SK")
    return resolved


def client_from_env(region: str = "cn-beijing") -> CPClient:
    """按公开 Region ID 构造固定生产 endpoint 的客户端。"""
    key = resolve_region(region)
    cfg = TARGETS[key]
    ak, sk = _resolve_credentials(key)
    return CPClient(
        endpoint=cfg["endpoint"],
        access_key=ak,
        secret_key=sk,
        service=cfg["service"],
        region=cfg["region"],
    )


def list_pipeline_runs(
    c: CPClient,
    workspace_id: str,
    pipeline_id: str,
    statuses: Optional[List[str]] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """滚动翻页拉取流水线运行记录（NextToken 分页）。"""
    items: List[Dict[str, Any]] = []
    next_token = ""
    while True:
        body: Dict[str, Any] = {
            "WorkspaceId": workspace_id,
            "PipelineId": pipeline_id,
            "MaxResults": min(max_results, 100),
        }
        if statuses:
            body["Filter"] = {"Statuses": statuses}
        if next_token:
            body["NextToken"] = next_token
        resp = c.call("ListPipelineRuns", body)
        result = resp.get("Result", {})
        batch = result.get("Items") or []
        items.extend(batch)
        next_token = result.get("NextToken") or ""
        if not next_token or not batch or len(items) >= max_results:
            break
    return items[:max_results]


def build_pipeline_filter(
    ids: Optional[List[str]] = None,
    name: Optional[str] = None,
    pipeline_group_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """构造 ListPipelines 的 Filter，空过滤条件返回 None。"""
    f: Dict[str, Any] = {}
    if ids:
        f["Ids"] = ids
    if name:
        f["Name"] = name
    if pipeline_group_id:
        f["PipelineGroupId"] = pipeline_group_id
    return f or None


def list_pipelines(
    c: CPClient,
    workspace_id: str,
    page_size: int = 100,
    max_results: Optional[int] = None,
    filter_: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """分页拉取工作区流水线列表，返回 (items, total_count)。

    ListPipelines 使用 PageNumber / PageSize 分页，PageSize 服务端限制 1~100。
    max_results=None 表示拉取所有页。
    """
    if page_size < 1 or page_size > 100:
        raise SystemExit("page_size 必须在 1~100 之间")
    items: List[Dict[str, Any]] = []
    page = 1
    total = 0
    while True:
        body: Dict[str, Any] = {
            "WorkspaceId": workspace_id,
            "PageNumber": page,
            "PageSize": page_size,
        }
        if filter_:
            body["Filter"] = filter_
        resp = c.call("ListPipelines", body)
        result = resp.get("Result", {})
        batch = result.get("Items") or []
        total = int(result.get("TotalCount") or 0)
        items.extend(batch)
        if max_results is not None and len(items) >= max_results:
            return items[:max_results], total
        if not batch or len(items) >= total:
            return items, total
        page += 1


def list_managed_app_change_records(
    c: CPClient,
    workspace_id: str,
    app_id: str,
    page_size: int = 100,
    max_results: Optional[int] = None,
    filter_: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Page through ListManagedAppChangeRecords without mutating caller input."""
    if page_size < 1 or page_size > 100:
        raise SystemExit("page_size 必须在 1~100 之间")
    if max_results is not None and max_results < 1:
        raise SystemExit("max_results 必须大于 0，或使用 None 获取全部记录")

    items: List[Dict[str, Any]] = []
    page = 1
    total = 0
    while True:
        body: Dict[str, Any] = {
            "WorkspaceId": workspace_id,
            "AppId": app_id,
            "PageNumber": page,
            "PageSize": page_size,
        }
        if filter_:
            body["Filter"] = copy.deepcopy(filter_)
        response = c.call("ListManagedAppChangeRecords", body)
        result, _ = extract_result(response)
        batch = result.get("Items") or []
        total = int(result.get("TotalCount") or 0)
        items.extend(batch)
        if max_results is not None and len(items) >= max_results:
            return items[:max_results], total
        if not batch or len(items) >= total:
            return items, total
        page += 1


def get_pipeline(c: CPClient, workspace_id: str, pipeline_id: str) -> Dict[str, Any]:
    """通过 ListPipelines + Id filter 获取单条流水线。"""
    items, _ = list_pipelines(
        c,
        workspace_id,
        page_size=1,
        max_results=1,
        filter_=build_pipeline_filter(ids=[pipeline_id]),
    )
    if not items:
        raise RuntimeError(f"Pipeline not found: {pipeline_id}")
    return items[0]


def update_pipeline_spec(c: CPClient, workspace_id: str, pipeline_id: str, spec: str) -> Dict[str, Any]:
    """仅更新流水线 Spec，避免误覆盖名称、资源、参数等其他配置。"""
    return c.call(
        "UpdatePipeline",
        {
            "WorkspaceId": workspace_id,
            "Id": pipeline_id,
            "Spec": spec,
        },
    )


def replace_once_idempotent(spec: str, old: str, new: str) -> Tuple[str, int, bool]:
    """对 spec 做幂等替换，返回 (new_spec, replacement_count, already_has_new)。

    若 old 后面已经紧跟 new 比 old 多出的后缀，则认为已替换过，避免重复追加。
    适用于类似 old -> old + suffix 的场景；其他场景退化为普通 replace。
    """
    if not old:
        raise SystemExit("replace-from 不能为空")
    already_has_new = new in spec
    if new.startswith(old):
        suffix = new[len(old):]
        if suffix:
            pattern = re.compile(re.escape(old) + r"(?!" + re.escape(suffix) + r")")
            out, count = pattern.subn(new, spec)
            return out, count, already_has_new
    count = spec.count(old)
    return spec.replace(old, new), count, already_has_new


def list_stages(
    c: CPClient, workspace_id: str, pipeline_id: str, pipeline_run_id: str
) -> List[Dict[str, Any]]:
    items, page, page_size = [], 1, 100
    while True:
        resp = c.call(
            "ListStages",
            {
                "WorkspaceId": workspace_id,
                "PipelineId": pipeline_id,
                "PipelineRunId": pipeline_run_id,
                "PageNumber": page,
                "PageSize": page_size,
            },
        )
        result = resp.get("Result", {})
        batch = result.get("Items") or []
        items.extend(batch)
        total = result.get("TotalCount", 0)
        if len(items) >= total or not batch:
            break
        page += 1
    return items


def list_task_runs(
    c: CPClient,
    workspace_id: str,
    pipeline_id: str,
    pipeline_run_id: str,
    task_id: str,
) -> List[Dict[str, Any]]:
    items, page, page_size = [], 1, 100
    while True:
        resp = c.call(
            "ListTaskRuns",
            {
                "WorkspaceId": workspace_id,
                "PipelineId": pipeline_id,
                "PipelineRunId": pipeline_run_id,
                "TaskId": task_id,
                "PageNumber": page,
                "PageSize": page_size,
            },
        )
        result = resp.get("Result", {})
        batch = result.get("Items") or []
        items.extend(batch)
        total = result.get("TotalCount", 0)
        if len(items) >= total or not batch:
            break
        page += 1
    return items


def list_agent_pools(
    c: CPClient, workspace_id: str, is_public: bool = True
) -> List[Dict[str, Any]]:
    """查询某工作区可见的构建集群（agentPool）。

    spec 里的 agentPool 取值为 'public/<Identifier>'（公共）或 'private/<Identifier>'。
    Filter 为必填，至少带 WorkspaceId；is_public 控制公共/私有。
    """
    items, page, page_size = [], 1, 100
    while True:
        resp = c.call(
            "ListAgentPools",
            {
                "Filter": {"WorkspaceId": workspace_id, "IsPublic": is_public},
                "PageNumber": page,
                "PageSize": page_size,
            },
        )
        result = resp.get("Result", {})
        batch = result.get("Items") or []
        items.extend(batch)
        total = result.get("TotalCount", 0)
        if len(items) >= total or not batch:
            break
        page += 1
    return items


if __name__ == "__main__":
    # quick self-check: python cp_api.py ping [cn-beijing|ap-southeast-1]
    if len(sys.argv) >= 2 and sys.argv[1] == "ping":
        region = sys.argv[2] if len(sys.argv) >= 3 else "cn-beijing"
        c = client_from_env(region)
        out = c.call("ListWorkspaces", {"PageNumber": 1, "PageSize": 1})
        print(json.dumps(redact_value(out), ensure_ascii=False, indent=2))
