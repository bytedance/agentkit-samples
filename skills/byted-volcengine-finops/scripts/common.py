#!/usr/bin/env python3
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import volcenginesdkbilling
import volcenginesdkcore


DEFAULT_ENV_PATH = os.path.expanduser("~/.openclaw/workspace/.env")
DEFAULT_REGION = "cn-beijing"


def load_env_file(env_path: str = DEFAULT_ENV_PATH) -> None:
    """用最小依赖读取 .env，避免额外安装 python-dotenv。"""
    if not env_path:
        return
    resolved_path = os.path.expanduser(env_path)
    if not os.path.exists(resolved_path):
        return
    with open(resolved_path, "r", encoding="utf-8") as file_obj:
        for raw_line in file_obj:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def require_credentials() -> None:
    """账单接口固定依赖 AK/SK，这里提前做显式校验。"""
    if os.getenv("VOLCENGINE_AK") and os.getenv("VOLCENGINE_SK"):
        return
    raise SystemExit("缺少 VOLCENGINE_AK 或 VOLCENGINE_SK，请先配置环境变量或 .env 文件。")


def validate_month(value: str, field_name: str) -> None:
    """校验 YYYY-MM 格式的月份字段。"""
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise SystemExit(f"{field_name} 格式非法，期望 YYYY-MM，实际为: {value}") from exc


def validate_date(value: str, field_name: str) -> None:
    """校验 YYYY-MM-DD 格式的日期字段。"""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(f"{field_name} 格式非法，期望 YYYY-MM-DD，实际为: {value}") from exc


def validate_pagination(limit: int, offset: int) -> None:
    """分页接口统一约束 Limit 和 Offset。"""
    if not 1 <= limit <= 300:
        raise SystemExit(f"Limit 超出范围，当前为 {limit}，允许范围是 1 到 300。")
    if offset < 0:
        raise SystemExit(f"Offset 不能为负数，当前为 {offset}。")


def validate_date_in_month(month_value: str, date_value: Optional[str], month_field: str, date_field: str) -> None:
    """校验日期字段是否落在指定月份中。"""
    validate_month(month_value, month_field)
    if not date_value:
        return
    validate_date(date_value, date_field)
    if date_value[:7] != month_value:
        raise SystemExit(f"{date_field} 必须与 {month_field} 处于同一月份，当前为 {month_value} / {date_value}。")


def validate_json_object_string(value: Optional[str], field_name: str) -> None:
    """校验字符串是否为 JSON 对象，避免把错误示例直接传给接口。"""
    if not value:
        return
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{field_name} 必须是合法的 JSON 字符串，当前值为: {value}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{field_name} 必须是 JSON 对象字符串，当前值为: {value}")


def build_billing_api(env_path: str = DEFAULT_ENV_PATH, region: str = "") -> volcenginesdkbilling.BILLINGApi:
    """统一初始化 Billing SDK，避免多个脚本重复样板代码。"""
    load_env_file(env_path)
    require_credentials()

    configuration = volcenginesdkcore.Configuration()
    configuration.ak = os.getenv("VOLCENGINE_AK")
    configuration.sk = os.getenv("VOLCENGINE_SK")
    configuration.region = region or os.getenv("VOLCENGINE_REGION", DEFAULT_REGION)
    volcenginesdkcore.Configuration.set_default(configuration)
    return volcenginesdkbilling.BILLINGApi()


def compact_request_kwargs(raw_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """去掉 None 和空列表，避免把无效筛选条件传进请求对象。"""
    compacted: Dict[str, Any] = {}
    for key, value in raw_kwargs.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        compacted[key] = value
    return compacted


def build_request_from_official_kwargs(request_cls: Any, raw_kwargs: Dict[str, Any]) -> Any:
    """允许脚本按官网参数名组织字典，再统一映射到 SDK 的 snake_case 字段。"""
    compacted = compact_request_kwargs(raw_kwargs)
    reverse_attribute_map = {api_name: sdk_name for sdk_name, api_name in getattr(request_cls, "attribute_map", {}).items()}
    sdk_kwargs: Dict[str, Any] = {}
    for key, value in compacted.items():
        sdk_key = reverse_attribute_map.get(key)
        if not sdk_key:
            raise SystemExit(f"{request_cls.__name__} 不支持参数 {key}，请检查官网文档或 SDK 字段映射。")
        sdk_kwargs[sdk_key] = value
    return request_cls(**sdk_kwargs)


def fetch_all_pages(
    api_instance: volcenginesdkbilling.BILLINGApi,
    request_cls: Any,
    list_method_name: str,
    raw_kwargs: Dict[str, Any],
    limit: int = 100,
) -> list:
    """通用翻页工具：自动按 Offset + Limit 拉取全量数据。

    Args:
        api_instance: 已初始化的 BILLINGApi 实例。
        request_cls: SDK 请求类（如 ListBillDetailRequest）。
        list_method_name: api_instance 上的方法名（如 "list_bill_detail"）。
        raw_kwargs: 除 Offset/Limit/NeedRecordNum 外的请求参数字典。
        limit: 单页数量，默认 100。

    Returns:
        全量记录列表（Result.List 的聚合结果）。
    """
    all_rows: list = []
    offset = 0
    while True:
        page_kwargs = {**raw_kwargs, "Limit": limit, "Offset": offset, "NeedRecordNum": 1}
        request = build_request_from_official_kwargs(request_cls, page_kwargs)
        method = getattr(api_instance, list_method_name)
        resp = method(request)
        result = resp.to_dict() if hasattr(resp, "to_dict") else resp
        rows = result.get("Result", {}).get("List", [])
        total = result.get("Result", {}).get("Total", -1)
        all_rows.extend(rows)
        if len(rows) < limit or (total >= 0 and len(all_rows) >= total):
            break
        offset += limit
    return all_rows


def print_response(response: Any) -> None:
    """统一把 SDK 响应转成结构化 JSON，方便后续分析和管道处理。"""
    if hasattr(response, "to_dict"):
        payload = response.to_dict()
    else:
        payload = response
    print(json.dumps(payload, ensure_ascii=False, indent=2))
