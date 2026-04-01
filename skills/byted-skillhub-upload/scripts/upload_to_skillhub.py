import argparse
import json
import logging
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


logger = logging.getLogger("skillhub_uploader")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stderr,
    )


def _normalize_api_base(api_base: str) -> str:
    formatted = api_base.strip()
    if not formatted.startswith("http://") and not formatted.startswith("https://"):
        formatted = f"http://{formatted}"
    return formatted.rstrip("/")


def _read_env() -> Tuple[str, str, Optional[str]]:
    api_host = os.getenv("ARK_SKILL_API_BASE")
    api_key = os.getenv("ARK_SKILL_API_KEY")
    skill_space_id = os.getenv("SKILLHUB_SKILL_SPACE_ID")
    if not api_host or not api_key:
        raise SystemExit("缺少必要环境变量: ARK_SKILL_API_BASE, ARK_SKILL_API_KEY")
    sid = skill_space_id.strip() if skill_space_id else None
    if not sid:
        sid = None
    logger.info(
        "读取环境变量: api_base=%s skill_space_id=%s api_key_len=%s",
        _normalize_api_base(api_host),
        sid or "-",
        len(api_key.strip()),
    )
    return _normalize_api_base(api_host), api_key.strip(), sid


def _sanitize_filename(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")
    return base or "skill"


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def _zip_directory(src_dir: Path) -> Path:
    if not src_dir.is_dir():
        raise SystemExit(f"目标不是目录: {src_dir}")
    tmp = tempfile.NamedTemporaryFile(prefix="skillhub_", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        count = 0
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in _iter_files(src_dir):
                arcname = str(file_path.relative_to(src_dir))
                zf.write(file_path, arcname)
                count += 1
        logger.info("已打包目录: dir=%s files=%s zip=%s", src_dir, count, tmp_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    return tmp_path


def _encode_multipart_formdata(
    fields: List[Tuple[str, str]],
    files: List[Tuple[str, str, bytes, str]],
) -> Tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    crlf = b"\r\n"
    body = bytearray()

    def _add_line(line: bytes) -> None:
        body.extend(line)
        body.extend(crlf)

    for name, value in fields:
        _add_line(f"--{boundary}".encode("utf-8"))
        _add_line(
            f'Content-Disposition: form-data; name="{name}"'.encode("utf-8")
        )
        _add_line(b"")
        _add_line(value.encode("utf-8"))

    for field_name, filename, content, content_type in files:
        _add_line(f"--{boundary}".encode("utf-8"))
        _add_line(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"'
            ).encode("utf-8")
        )
        _add_line(f"Content-Type: {content_type}".encode("utf-8"))
        _add_line(b"")
        body.extend(content)
        body.extend(crlf)

    _add_line(f"--{boundary}--".encode("utf-8"))
    content_type = f"multipart/form-data; boundary={boundary}"
    return bytes(body), content_type


def _safe_decode(data: bytes, limit: int = 4096) -> str:
    chunk = data[:limit]
    text = chunk.decode("utf-8", errors="replace")
    if len(data) > limit:
        return f"{text}...[truncated {len(data) - limit} bytes]"
    return text


def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    redacted: Dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() == "authorization":
            redacted[k] = "Bearer ***"
        else:
            redacted[k] = v
    return redacted


@dataclass
class HttpResponse:
    status: int
    headers: Dict[str, str]
    body: bytes


def _post_multipart(url: str, data: bytes, content_type: str, api_key: str) -> HttpResponse:
    headers = {
        "Content-Type": content_type,
        "Authorization": f"Bearer {api_key}",
        "ServiceName": "skillhub",
        "Accept": "application/json",
    }
    logger.info("发起请求: url=%s bytes=%s", url, len(data))
    logger.debug("请求头: %s", _redact_headers(headers))
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            status = int(getattr(resp, "status", 0) or 0)
            resp_headers = {k: v for k, v in getattr(resp, "headers", {}).items()}
            logger.info("收到响应: status=%s bytes=%s", status or "-", len(raw))
            logger.debug("响应头: %s", resp_headers)
            logger.debug("响应体(预览): %s", _safe_decode(raw))
            return HttpResponse(status=status, headers=resp_headers, body=raw)
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        status = int(getattr(e, "code", 0) or 0)
        resp_headers = {k: v for k, v in getattr(e, "headers", {}).items()}
        logger.error("收到 HTTP 错误响应: status=%s bytes=%s", status or "-", len(raw))
        logger.debug("响应头: %s", resp_headers)
        logger.debug("响应体(预览): %s", _safe_decode(raw))
        return HttpResponse(status=status, headers=resp_headers, body=raw)
    except urllib.error.URLError as e:
        raise SystemExit(f"请求失败: {e}") from e


def _unwrap_response_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "Id" in payload or "SkillVersionId" in payload:
        return payload
    for k in ("Result", "Response", "Data", "data"):
        v = payload.get(k)
        if isinstance(v, dict) and ("Id" in v or "SkillVersionId" in v):
            return v
    return payload


@dataclass
class CreateSkillResponse:
    Id: str
    SkillVersionId: str
    RequestId: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CreateSkillResponse":
        request_id: Optional[str] = None
        meta = payload.get("ResponseMetadata")
        if isinstance(meta, dict):
            action = meta.get("Action")
            if action is not None and action != "CreateSkill":
                raise SystemExit(f"CreateSkill 响应 Action 异常: {action}")
            request_id_val = meta.get("RequestId")
            if isinstance(request_id_val, str) and request_id_val:
                request_id = request_id_val
            err = meta.get("Error")
            if isinstance(err, dict):
                code = err.get("Code")
                msg = err.get("Message")
                if isinstance(code, str) and code and isinstance(msg, str) and msg:
                    raise SystemExit(f"CreateSkill 失败: {code}: {msg} (RequestId={request_id or '-'})")

        obj = payload.get("Result") if isinstance(payload.get("Result"), dict) else _unwrap_response_dict(payload)
        logger.debug("CreateSkill 原始 JSON keys=%s", sorted(payload.keys()))
        if isinstance(meta, dict):
            logger.debug("CreateSkill ResponseMetadata=%s", meta)
        logger.debug(
            "CreateSkill 解析对象: type=%s keys=%s",
            type(obj).__name__,
            sorted(obj.keys()) if isinstance(obj, dict) else "-",
        )
        if isinstance(obj, dict):
            skill_id = obj.get("Id") or obj.get("id") or obj.get("SkillId") or obj.get("SkillID")
            version_id = (
                obj.get("SkillVersionId")
                or obj.get("skillVersionId")
                or obj.get("SkillVersionID")
                or obj.get("VersionId")
            )
        else:
            skill_id = None
            version_id = None
        if not isinstance(skill_id, str) or not skill_id:
            logger.error(
                "CreateSkill 响应缺少有效的 Id: request_id=%s payload_keys=%s",
                request_id or "-",
                sorted(payload.keys()),
            )
            raise SystemExit("CreateSkill 响应缺少有效的 Id")
        if not isinstance(version_id, str) or not version_id:
            logger.error(
                "CreateSkill 响应缺少有效的 SkillVersionId: request_id=%s payload_keys=%s",
                request_id or "-",
                sorted(payload.keys()),
            )
            raise SystemExit("CreateSkill 响应缺少有效的 SkillVersionId")
        return cls(Id=skill_id, SkillVersionId=version_id, RequestId=request_id)


def create_skill(
    api_host: str,
    api_key: str,
    name: str,
    description: Optional[str],
    skill_space_ids: List[str],
    zip_bytes: bytes,
) -> CreateSkillResponse:
    url = f"{api_host}/CreateSkill"
    logger.info(
        "准备上传: name=%s description=%s skill_spaces=%s zip_bytes=%s",
        name,
        "Y" if description else "N",
        len(skill_space_ids),
        len(zip_bytes),
    )
    fields: List[Tuple[str, str]] = [("Name", name)]
    if description:
        fields.append(("Description", description))
    for sid in skill_space_ids:
        fields.append(("SkillSpaces", sid))
    filename = f"{_sanitize_filename(name)}.zip"
    body, content_type = _encode_multipart_formdata(
        fields=fields,
        files=[("Zip", filename, zip_bytes, "application/zip")],
    )
    http_resp = _post_multipart(url=url, data=body, content_type=content_type, api_key=api_key)
    try:
        data = json.loads(http_resp.body.decode("utf-8"))
    except Exception:
        raise SystemExit("CreateSkill 响应不是有效的 JSON")
    if not isinstance(data, dict):
        raise SystemExit("CreateSkill 响应 JSON 结构异常")
    logger.debug("CreateSkill HTTP status=%s headers=%s", http_resp.status or "-", http_resp.headers)
    resp = CreateSkillResponse.from_dict(data)
    logger.info(
        "解析完成: id=%s version_id=%s request_id=%s",
        resp.Id,
        resp.SkillVersionId,
        resp.RequestId or "-",
    )
    return resp


def main() -> None:
    parser = argparse.ArgumentParser(prog="upload_to_skillhub")
    parser.add_argument("--path", required=True, help="待上传 skill 路径（目录或 .zip 文件）")
    parser.add_argument("--name", help="Skill 名称。默认取目录名/zip 文件名")
    parser.add_argument("--description", default="", help="Skill 描述")
    parser.add_argument("--verbose", dest="verbose", action="store_true", default=True, help="打印更详细日志")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    api_host, api_key, space_id = _read_env()

    target = Path(args.path)
    if not target.exists():
        raise SystemExit(f"路径不存在: {target}")

    zip_path: Optional[Path] = None
    temp_zip: Optional[Path] = None
    if target.is_dir():
        temp_zip = _zip_directory(target)
        zip_path = temp_zip
    elif target.is_file() and target.suffix.lower() == ".zip":
        zip_path = target
    else:
        raise SystemExit("目标必须是目录或 .zip 文件")

    name = (args.name or (target.name if target.is_dir() else target.stem)).strip()
    if not name:
        raise SystemExit("Skill 名称为空，请通过 --name 指定")
    logger.info("参数确认: path=%s name=%s zip=%s", target, name, zip_path)

    try:
        zip_bytes = zip_path.read_bytes() if zip_path else b""
        if not zip_bytes:
            raise SystemExit("Zip 内容为空")
        resp = create_skill(
            api_host=api_host,
            api_key=api_key,
            name=name,
            description=args.description.strip() or None,
            skill_space_ids=[space_id] if space_id else [],
            zip_bytes=zip_bytes,
        )
    finally:
        if temp_zip:
            try:
                temp_zip.unlink(missing_ok=True)
            except Exception:
                pass

    print(f"Id: {resp.Id}")
    print(f"SkillVersionId: {resp.SkillVersionId}")
    if resp.RequestId:
        print(f"RequestId: {resp.RequestId}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = ""
        raise SystemExit(f"HTTP 错误: {e.code} {e.reason} {detail}".strip())
    except urllib.error.URLError as e:
        raise SystemExit(f"网络错误: {e.reason}")
    except KeyboardInterrupt:
        raise SystemExit("已中断")
