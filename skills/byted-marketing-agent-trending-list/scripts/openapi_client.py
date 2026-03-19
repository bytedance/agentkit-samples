#!/usr/bin/env python3
# Copyright 2024 ByteDance, Inc.
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
from __future__ import annotations

import argparse
import logging
import json
import os
import re
import sys
import time
from typing import Any, Dict, Optional


DEFAULT_API_HOST = "cdp-saas.cn-beijing.volcengineapi.com"
DEFAULT_API_PATH = "/"
DEFAULT_SERVICE = "cdp_saas"
DEFAULT_REGION = "cn-beijing"
DEFAULT_ACTION = "ArkOpenClawSkill"
DEFAULT_VERSION = "2022-08-01"
MIN_VOLC_SDK_VERSION = "4.0.43"

_SENSITIVE_KEY_RE = re.compile(r"(token|secret|password|passwd|api[_-]?key|task[_-]?id)", re.IGNORECASE)

# ── 字段别名映射：中文名 → 英文字段名 ──────────────────────────────────────────
_FIELD_ALIAS_HOT_TOPIC: Dict[str, str] = {
    "主话题":       "main_challenge",
    "关联挑战1":    "assoc_challenge_1",
    "关联挑战2":    "assoc_challenge_2",
    "关联挑战3":    "assoc_challenge_3",
    "关联挑战4":    "assoc_challenge_4",
    "关联挑战5":    "assoc_challenge_5",
    "占比1":        "ratio_1",
    "占比2":        "ratio_2",
    "占比3":        "ratio_3",
    "占比4":        "ratio_4",
    "占比5":        "ratio_5",
    "是否官方":     "is_official",
    "是否商业":     "is_commerce",
    "相关视频标题": "item_titles",
    "相关视频数量": "item_count",
    "总播放量":     "total_vv_all",
    "总点赞数":     "total_like_cnt_all",
    "总评论数":     "total_comment_cnt_all",
    "总分享数":     "total_share_cnt_all",
    "总关注数":     "total_follow_cnt_all",
    "总收藏数":     "total_favourite_cnt_all",
    "总完播量":     "total_finish_vv_all",
    "话题描述":     "desc_info",
    "产出日期":     "p_date",
    "任务名":       "task_name",
    "任务日期":     "task_date",
    "任务ID":       "task_id",
}

_FIELD_ALIAS_HOT_EVENT: Dict[str, str] = {
    "事件名称":     "event_name",
    "摘要":         "brief",
    "相关视频":     "related_videos",
    "链接":         "url",
    "热度值":       "heat_value",
    "排名":         "rank",
    "语音文本":     "asr",
    "分析内容":     "analysis",
    "产出日期":     "p_date",
    "任务名":       "task_name",
    "任务日期":     "task_date",
}

_FIELD_ALIAS_HOT_TOPIC_REVERSE: Dict[str, str] = {v: k for k, v in _FIELD_ALIAS_HOT_TOPIC.items()}
_FIELD_ALIAS_HOT_EVENT_REVERSE: Dict[str, str] = {v: k for k, v in _FIELD_ALIAS_HOT_EVENT.items()}


def _translate_field_expr(expr: Optional[str], alias: Dict[str, str]) -> Optional[str]:
    """将表达式中的中文字段名替换为英文字段名（order_by / filter 通用）。
    按中文名长度降序替换，避免短名称干扰长名称。
    """
    if not expr:
        return expr
    result = expr
    for cn, en in sorted(alias.items(), key=lambda x: -len(x[0])):
        result = result.replace(cn, en)
    return result


def _rename_keys(obj: Any, reverse: Dict[str, str]) -> Any:
    """递归将响应数据中的英文 key 替换为中文 key。"""
    if isinstance(obj, dict):
        return {reverse.get(k, k): _rename_keys(v, reverse) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rename_keys(i, reverse) for i in obj]
    return obj


def _debug_enabled() -> bool:
    v = _env("OPENCLAW_DEBUG")
    return str(v).lower() in ("1", "true", "yes", "on") if v is not None else False


def _env(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v is None:
        return None
    v = v.strip()
    return v or None


def _mask_secret(s: Optional[str]) -> Optional[str]:
    """对敏感字符串做脱敏展示：仅保留前后少量字符。"""
    if not s:
        return None
    ss = str(s)
    if len(ss) <= 8:
        return "*" * len(ss)
    return ss[:4] + "*" * (len(ss) - 8) + ss[-4:]


def _parse_version(v: str) -> tuple[int, int, int]:
    parts = (v or "").strip().split(".")
    nums: list[int] = []
    for p in parts[:3]:
        try:
            nums.append(int(re.sub(r"\D.*$", "", p)))
        except Exception:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def _get_volc_sdk_version() -> Optional[str]:
    try:
        from importlib.metadata import version  # py3.8+
    except Exception:
        try:
            from importlib_metadata import version  # type: ignore
        except Exception:
            return None
    try:
        return version("volcengine-python-sdk")
    except Exception:
        return None


def _ensure_volc_sdk_min_version(min_version: str = MIN_VOLC_SDK_VERSION) -> Optional[str]:
    cur = _get_volc_sdk_version()
    if not cur:
        return "未安装 volcengine-python-sdk。请先安装 volcengine-python-sdk>=4.0.43。"
    if _parse_version(cur) < _parse_version(min_version):
        return f"volcengine-python-sdk 版本过低（当前 {cur}，要求 >= {min_version}）。请升级以避免历史版本重试缺陷。"
    return None


def _build_api_client(ak_override: Optional[str] = None, sk_override: Optional[str] = None) -> tuple[Any, str]:
    """构建已配置签名的 volcenginesdkcore.ApiClient，返回 (client, api_path)。"""
    ver_err = _ensure_volc_sdk_min_version()
    if ver_err:
        raise RuntimeError(ver_err)

    try:
        import volcenginesdkcore  # type: ignore
    except ImportError:
        raise RuntimeError(
            "未安装 volcengine-python-sdk（缺少 volcenginesdkcore）。请先安装 volcengine-python-sdk>=4.0.43。"
        )

    ak = ak_override or _env("VOLCENGINE_ACCESS_KEY")
    sk = sk_override or _env("VOLCENGINE_SECRET_KEY")

    if not (ak and sk):
        raise RuntimeError("未配置 Volcengine 凭证（需要同时设置 VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY）。")


    # service / region / host 均有内置默认值，环境变量可覆盖（用于调试）
    service = _env("VOLC_SERVICE") or DEFAULT_SERVICE
    region = _env("VOLCENGINE_REGION") or DEFAULT_REGION

    custom_url = _env("PUBLIC_INSIGHT_API_URL")
    if custom_url:
        from urllib.parse import urlsplit
        p = urlsplit(custom_url)
        host = p.netloc or DEFAULT_API_HOST
        api_path = p.path or DEFAULT_API_PATH
        scheme = p.scheme or "https"
    else:
        host = DEFAULT_API_HOST
        api_path = DEFAULT_API_PATH
        scheme = "https"

    configuration = volcenginesdkcore.Configuration()
    # 默认关闭 SDK 的日志输出（避免干扰用户输出）。
    # 调试时可通过 OPENCLAW_DEBUG=1 打开。
    if not _debug_enabled():
        try:
            configuration.logger["package_logger"].setLevel(logging.ERROR)
            configuration.logger["urllib3_logger"].setLevel(logging.ERROR)
        except Exception:
            pass
    configuration.ak = ak
    configuration.sk = sk
    configuration.region = region
    configuration.host = host
    if scheme != "https":
        configuration.scheme = scheme
    if hasattr(configuration, "service"):
        configuration.service = service

    return volcenginesdkcore.ApiClient(configuration), api_path


def _do_call(api_client: Any, api_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """通过 SDK ApiClient 向火山 OpenAPI 发起签名 POST 请求。"""
    # SDK call_api 拦截器把 202 当异常处理（期望 200），改用 rest_client 直接发，
    # 仍通过 SDK SignerV4 签名，保持 SDK 依赖。
    try:
        from volcenginesdkcore.signv4 import SignerV4  # type: ignore
    except ImportError:
        return {"status": "error", "message": "未安装 volcengine-python-sdk。"}

    try:
        cfg = api_client.configuration
        body_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        scheme = getattr(cfg, "scheme", "https") or "https"
        service = getattr(cfg, "service", DEFAULT_SERVICE) or DEFAULT_SERVICE
        url = f"{scheme}://{cfg.host}{api_path}"
        query = [("Action", DEFAULT_ACTION), ("Version", DEFAULT_VERSION)]

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Host": cfg.host,
        }
        SignerV4.sign(api_path, "POST", headers, body_str, None, query,
                      cfg.ak, cfg.sk, cfg.region, service, None)

        # 拼装完整 URL（含 query string）
        from urllib.parse import urlencode
        full_url = f"{url}?{urlencode(query)}"

        import urllib.request as _urllib
        import urllib.error as _urlerr
        req = _urllib.Request(full_url, data=body_str.encode(), headers=headers, method="POST")
        try:
            http_resp = _urllib.urlopen(req, timeout=60)
            status = http_resp.status
            raw = http_resp.read()
        except _urlerr.HTTPError as http_err:
            status = http_err.code
            raw = http_err.read()

        try:
            data = json.loads(raw.decode())
        except Exception:
            return {"status": "error", "message": f"服务返回非 JSON（HTTP {status}）。"}
        if status >= 400:
            msg = f"服务请求失败（HTTP {status}）。"
            meta = data.get("ResponseMetadata") if isinstance(data, dict) else None
            if isinstance(meta, dict) and isinstance(meta.get("Error"), dict):
                err = meta["Error"]
                code = str(err.get("Code") or err.get("CodeN") or "").lower()
                if code in ("invalidcredential", "100025"):
                    msg = "鉴权失败：请检查 AK/SK 凭证配置是否正确。"
            return {"status": "error", "message": msg, "data": data}
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": f"请求失败：{str(e)[:200]}"}


def _is_retryable(resp: Dict[str, Any]) -> bool:
    """判断响应是否可重试（502/503/504 或 InternalServiceError）。"""
    if resp.get("status") == "success":
        return False
    msg = resp.get("message", "")
    if "HTTP 502" in msg or "HTTP 503" in msg or "HTTP 504" in msg:
        return True
    data = resp.get("data")
    if isinstance(data, dict):
        meta = data.get("ResponseMetadata")
        if isinstance(meta, dict):
            err = meta.get("Error", {})
            code = str(err.get("Code") or err.get("CodeN") or "")
            if code in ("InternalServiceError", "100023"):
                return True
    return False


def api_call(tool_name: str, arguments: Dict[str, Any], ak: Optional[str] = None, sk: Optional[str] = None) -> Dict[str, Any]:
    """封装单次工具调用：MCP JSON-RPC → SDK 签名发送 → 解析响应（含重试）。"""
    try:
        api_client, api_path = _build_api_client(ak_override=ak, sk_override=sk)
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    # 后端是 MCP 服务，body 保持 JSON-RPC 2.0 格式
    payload = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    max_retries = 3
    for attempt in range(max_retries + 1):
        resp = _do_call(api_client, api_path, payload)
        if not _is_retryable(resp) or attempt == max_retries:
            break
        wait = 2 ** attempt  # 1s, 2s, 4s
        time.sleep(wait)
    if resp.get("status") != "success":
        return resp

    data = resp.get("data")
    if not isinstance(data, dict):
        return {"status": "error", "message": "响应格式异常。"}

    # JSON-RPC 错误结构
    if data.get("error"):
        return {"status": "error", "message": str(data["error"].get("message") or data["error"])}

    result = data.get("result")
    if not isinstance(result, dict):
        return {"status": "error", "message": "响应缺少 result。"}
    if result.get("isError") is True:
        return {"status": "error", "message": "服务返回错误。", "data": result}

    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            txt = first.get("text")
            if isinstance(txt, str):
                try:
                    return {"status": "success", "data": json.loads(txt)}
                except Exception:
                    return {"status": "success", "data": {"raw": txt}}

    return {"status": "success", "data": result}


def list_categories(ak: Optional[str] = None, sk: Optional[str] = None) -> Dict[str, Any]:
    resp = api_call("list_categories", {}, ak=ak, sk=sk)
    if resp.get("status") != "success":
        return resp
    data = resp.get("data")
    if isinstance(data, dict) and data.get("ok") is True:
        return {"status": "success", "categories": data.get("categories")}
    return {"status": "success", "categories": (data.get("categories") if isinstance(data, dict) else data)}


def query_clickhouse_http(
    *,
    category: str,
    query_type: str,
    task_date: Optional[str],
    filter_str: Optional[str],
    order_by: Optional[str],
    page: int,
    page_size: int,
    ak: Optional[str] = None,
    sk: Optional[str] = None,
) -> Dict[str, Any]:
    if query_type not in ("hot_topic_insights", "hot_event"):
        return {"status": "error", "message": "本接口仅支持 query_type=hot_topic_insights 或 hot_event。"}

    alias = _FIELD_ALIAS_HOT_TOPIC if query_type == "hot_topic_insights" else _FIELD_ALIAS_HOT_EVENT
    reverse = _FIELD_ALIAS_HOT_TOPIC_REVERSE if query_type == "hot_topic_insights" else _FIELD_ALIAS_HOT_EVENT_REVERSE

    en_order_by = _translate_field_expr(order_by, alias)
    en_filter = _translate_field_expr(filter_str, alias)

    args: Dict[str, Any] = {
        "category": category,
        "query_type": query_type,
        "page": page,
        "page_size": page_size,
    }
    if task_date:
        args["task_date"] = task_date
    if en_filter:
        args["filter"] = en_filter
    if en_order_by:
        args["order_by"] = en_order_by

    resp = api_call("query_clickhouse_http", args, ak=ak, sk=sk)
    if resp.get("status") == "success":
        resp["data"] = _rename_keys(resp.get("data"), reverse)
    return resp


def _is_safe_kv(k: str, v: Any) -> bool:
    if _SENSITIVE_KEY_RE.search(k or ""):
        return False
    if isinstance(v, str) and len(v) > 2000:
        return False
    return True


def _pick_first(d: Dict[str, Any], keys: list[str]) -> Optional[Any]:
    for k in keys:
        if k in d and d.get(k) not in (None, ""):
            return d.get(k)
    return None


def _extract_items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            return data.get("data")
        for k in ("items", "list", "rows", "result"):
            v = data.get(k)
            if isinstance(v, list):
                return v
    return []


def _format_categories_text(categories: Any, max_items: int) -> str:
    items: list[Any]
    if isinstance(categories, list):
        items = categories
    elif categories is None:
        items = []
    else:
        items = [categories]
    lines = [f"可选行业（{len(items)}）："]
    for i, it in enumerate(items[:max_items], start=1):
        lines.append(f"{i}. {it}")
    if len(items) > max_items:
        lines.append(f"… 另有 {len(items) - max_items} 个行业未展示")
    return "\n".join(lines) if items else "暂无可用行业。"


def _format_list_text(data: Any, max_items: int) -> str:
    items = _extract_items(data)
    if not items:
        return "暂无数据。"
    lines = [f"列表结果（{len(items)} 条，展示前 {min(len(items), max_items)} 条）："]
    for idx, it in enumerate(items[:max_items], start=1):
        if isinstance(it, dict):
            title = _pick_first(it, ["item_title", "itemTitle", "title", "name", "event_name", "eventName", "brief"])
            url = _pick_first(it, ["url", "link"])
            rank = _pick_first(it, ["rank", "ranking"])
            heat = _pick_first(it, ["heat_value", "heatValue", "heat", "hot", "score"])
            vv = _pick_first(it, ["vv", "vv_all", "play", "views", "play_cnt", "playCount"])

            parts = []
            if title:
                parts.append(str(title))
            if rank not in (None, ""):
                parts.append(f"rank={rank}")
            if heat not in (None, ""):
                parts.append(f"heat={heat}")
            if vv not in (None, ""):
                parts.append(f"vv={vv}")
            if url:
                parts.append(str(url))
            if not parts:
                safe_pairs = [(k, v) for k, v in it.items() if isinstance(k, str) and _is_safe_kv(k, v)]
                preview = ", ".join([f"{k}={v}" for k, v in safe_pairs[:4]])
                parts = [preview or "(无法展示字段)"]
            lines.append(f"{idx}. " + " | ".join(parts))
        else:
            lines.append(f"{idx}. {it}")
    if len(items) > max_items:
        lines.append(f"… 其余 {len(items) - max_items} 条未展示")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="MarketingAgent OpenAPI Client (volcengine-sdk)")
    ap.add_argument("--format", default="text", choices=["text", "json"], help="输出格式")
    ap.add_argument("--max-items", type=int, default=20, help="text 输出时最多展示条数")
    ap.add_argument("--debug", action="store_true", help="输出完整错误信息（也可用 OPENCLAW_DEBUG=1）")
    ap.add_argument("--ak", default=None, help="Volcengine AccessKey（优先级高于环境变量和 .env 文件）")
    ap.add_argument("--sk", default=None, help="Volcengine SecretKey（优先级高于环境变量和 .env 文件）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-industries", help="获取可用行业枚举")

    q = sub.add_parser("query", help="按行业查询数据")
    q.add_argument("--category", required=True, help="行业")
    q.add_argument("--query-type", required=True, choices=["hot_topic_insights", "hot_event"], help="查询类型")
    q.add_argument("--task-date", default=None, help="任务日期 YYYY-MM-DD（可选）")
    q.add_argument("--filter", default=None, help="可选：过滤表达式字符串（例：vv > 1000）")
    q.add_argument("--order-by", default=None, help="排序字段（例：total_vv_all DESC 或 rank ASC）；hot_topic_insights 默认 total_vv_all DESC，hot_event 默认 rank DESC")
    q.add_argument("--page", type=int, default=1)
    q.add_argument("--page-size", type=int, default=20)

    args = ap.parse_args()

    if args.debug and not _debug_enabled():
        os.environ["OPENCLAW_DEBUG"] = "1"

    if args.cmd == "list-industries":
        out = list_categories(ak=args.ak, sk=args.sk)
        if args.format == "json":
            json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
            return 0
        if out.get("status") != "success":
            sys.stdout.write(str(out.get("message") or "请求失败"))
            if args.debug and out.get("data") is not None:
                sys.stdout.write("\n")
                sys.stdout.write(json.dumps(out.get("data"), ensure_ascii=False, indent=2))
            return 1
        sys.stdout.write(_format_categories_text(out.get("categories"), args.max_items))
        return 0

    if args.cmd == "query":
        out = query_clickhouse_http(
            category=args.category,
            query_type=args.query_type,
            task_date=args.task_date,
            filter_str=args.filter,
            order_by=args.order_by,
            page=args.page,
            page_size=args.page_size,
            ak=args.ak,
            sk=args.sk,
        )
        if args.format == "json":
            json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
            return 0 if out.get("status") == "success" else 1
        if out.get("status") != "success":
            sys.stdout.write(str(out.get("message") or "请求失败"))
            if args.debug and out.get("data") is not None:
                sys.stdout.write("\n")
                sys.stdout.write(json.dumps(out.get("data"), ensure_ascii=False, indent=2))
            return 1
        sys.stdout.write(_format_list_text(out.get("data"), args.max_items))
        return 0

    sys.stdout.write("unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
