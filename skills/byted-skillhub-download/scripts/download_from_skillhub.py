import argparse
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


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
    return _normalize_api_base(api_host), api_key.strip(), sid


def _post_json(
    url: str,
    payload: Dict[str, Any],
    api_key: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[bytes, Dict[str, str]]:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "ServiceName": "skillhub",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        resp_headers = {k: v for k, v in resp.getheaders()}
        return body, resp_headers


def _json_loads_or_none(data: bytes) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")


def list_skills(
    api_host: str, api_key: str, skill_space_id: Optional[str], name: str
) -> Dict[str, Any]:
    url = f"{api_host}/ListSkills"
    filter_obj: Dict[str, Any] = {"Name": name}
    if skill_space_id:
        filter_obj["SkillSpaceId"] = skill_space_id
    payload: Dict[str, Any] = {
        "PageNumber": 1,
        "PageSize": 50,
        "Filter": filter_obj,
    }
    print(f"[DEBUG] 调用 ListSkills: url={url}")
    print(f"[DEBUG] 请求 payload: {json.dumps(payload, ensure_ascii=False)}")
    body, resp_headers = _post_json(url, payload, api_key)
    print(f"[DEBUG] 响应头: {resp_headers}")
    print(f"[DEBUG] 响应体长度: {len(body)} 字节")
    try:
        body_str = body.decode("utf-8")
        print(f"[DEBUG] 响应体前 1000 字符: {body_str[:1000]}...")
    except Exception as e:
        print(f"[DEBUG] 响应体解码失败: {e}")
    data = _json_loads_or_none(body)
    if not data:
        raise SystemExit("ListSkills 响应不是有效的 JSON")
    # 处理可能的响应包装结构
    if "Items" not in data:
        print(f"[DEBUG] 响应 JSON: {json.dumps(data, ensure_ascii=False)}")
        # 尝试从 Result 或 Response 字段获取
        wrapped = None
        if "Result" in data and isinstance(data["Result"], dict):
            print("[DEBUG] 尝试从 Result 字段获取 Items")
            wrapped = data["Result"]
        elif "Response" in data and isinstance(data["Response"], dict):
            print("[DEBUG] 尝试从 Response 字段获取 Items")
            wrapped = data["Response"]

        if wrapped and "Items" in wrapped:
            data = wrapped
        else:
            raise SystemExit("ListSkills 响应不包含 Items 字段")
    print(f"[DEBUG] Items 数量: {len(data.get('Items', []))}")
    return data


def pick_exact_skill(data: Dict[str, Any], name: str) -> Dict[str, Any]:
    items = data.get("Items") or []
    exact = [it for it in items if isinstance(it, dict) and it.get("Name") == name]
    if not exact:
        raise SystemExit(f"未找到名称精确匹配的 skill: {name}")
    return exact[0]


def extract_version_info(skill: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    version_id = None
    version_str = None
    lvs = skill.get("LatestVersionStatus") or {}
    if isinstance(lvs, dict):
        for k in ("VersionId", "VersionID", "Id", "ID"):
            if k in lvs and isinstance(lvs[k], str) and lvs[k]:
                version_id = lvs[k]
                break
        for k in ("Version",):
            if k in lvs and isinstance(lvs[k], str) and lvs[k]:
                version_str = lvs[k]
                break
    if not version_str:
        versions = skill.get("Versions")
        if isinstance(versions, list) and versions:
            version_str = str(versions[-1])
    if not version_str:
        vins = skill.get("VersionsInfo")
        if isinstance(vins, list) and vins:
            last = vins[-1]
            if isinstance(last, dict) and isinstance(last.get("Version"), str):
                version_str = last.get("Version")
            for k in ("VersionId", "VersionID", "Id", "ID"):
                if (
                    isinstance(last, dict)
                    and isinstance(last.get(k), str)
                    and last.get(k)
                ):
                    version_id = last.get(k)
                    break
    return version_id, version_str


def download_skill(
    api_host: str, api_key: str, skill_id: str, version_id: Optional[str]
) -> Tuple[bytes, Dict[str, str]]:
    url = f"{api_host}/DownloadSkill"
    payload: Dict[str, Any] = {"SkillId": skill_id, "IsPreview": False}
    if version_id:
        payload["SkillVersionId"] = version_id
    print(f"[DEBUG] 调用 DownloadSkill: url={url}")
    print(f"[DEBUG] 请求 payload: {json.dumps(payload, ensure_ascii=False)}")
    body, headers = _post_json(
        url,
        payload,
        api_key,
        extra_headers={"X-Skill-Caller": "arkclaw-business"},
    )
    print(f"[DEBUG] 响应头: {headers}")
    print(f"[DEBUG] 响应体长度: {len(body)} 字节")
    ctype = (headers.get("Content-Type") or "").lower()
    print(f"[DEBUG] Content-Type: {ctype}")
    # 优先尝试按二进制流处理
    if "application/json" in ctype:
        print("[DEBUG] 响应为 JSON，尝试解析")
        data = _json_loads_or_none(body)
        if isinstance(data, dict) and data.get("ZipBase64"):
            import base64

            print(f"[DEBUG] 检测到 ZipBase64 字段，长度: {len(data['ZipBase64'])} 字符")
            return base64.b64decode(data["ZipBase64"]), headers
        # 若 JSON 不包含 ZipBase64，仍按二进制流处理（可能是错误信息但保持兼容）
        print("[DEBUG] JSON 不包含 ZipBase64，按二进制流处理")
    else:
        print("[DEBUG] 响应为二进制流，直接返回")
    return body, headers


def main():
    parser = argparse.ArgumentParser(prog="download_from_skillhub")
    parser.add_argument("--name", required=True, help="Skill 名称，精确匹配")
    parser.add_argument(
        "--output", default="/root/.openclaw/workspace/skills/", help="输出路径。可为目录或文件名"
    )
    parser.add_argument(
        "--no-extract", action="store_true", help="只下载 zip 包，不自动解压"
    )
    args = parser.parse_args()

    api_host, api_key, space_id = _read_env()
    data = list_skills(api_host, api_key, space_id, args.name)
    skill = pick_exact_skill(data, args.name)

    skill_id = skill.get("Id")
    skill_name = skill.get("Name", args.name)  # 优先使用 API 返回的名称
    if not isinstance(skill_id, str) or not skill_id:
        raise SystemExit("ListSkills 返回的 Skill 未包含有效的 Id")

    version_id, version_str = extract_version_info(skill)
    zip_bytes, _ = download_skill(api_host, api_key, skill_id, version_id)

    out_path = Path(args.output)
    base = _sanitize_name(skill_name)

    if args.no_extract:
        # 只下载 zip 包逻辑
        if out_path.exists() and out_path.is_dir():
            file_path = out_path / f"{base}.zip"
        else:
            if str(out_path).endswith(os.sep) or str(out_path).endswith("/"):
                out_path = Path(str(out_path).rstrip("/"))
            if out_path.suffix.lower() != ".zip":
                out_path = out_path.with_suffix(".zip")
            file_path = out_path

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(zip_bytes)
        print(str(file_path))
    else:
        # 下载并解压逻辑
        target_dir = (
            out_path
            if not out_path.is_dir() and not out_path.exists()
            else out_path / base
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        # 使用临时文件保存 zip
        temp_zip = target_dir / f"{base}.zip.tmp"
        with open(temp_zip, "wb") as f:
            f.write(zip_bytes)

        # 解压
        try:
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(target_dir)

            # 尝试平铺：如果解压后只有一个顶层目录，将其内容移动到上一级
            items = [it for it in target_dir.iterdir() if it.name != temp_zip.name]
            if len(items) == 1 and items[0].is_dir():
                inner_dir = items[0]
                for child in inner_dir.iterdir():
                    shutil.move(str(child), str(target_dir))
                inner_dir.rmdir()

            print(f"[DEBUG] 已解压至目录: {target_dir}")
        finally:
            if temp_zip.exists():
                temp_zip.unlink()

        print(str(target_dir))


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
