"""
Database Toolbox - 纯函数式 API

提供独立函数与 ToolboxClient 配合使用，用于与火山引擎 Database Workbench API 交互。
所有函数无状态，不修改传入参数。

核心设计原则：
1. 所有函数返回统一的字典格式 {success, message, data, context}
2. 函数无副作用（除写入缓存文件外）
3. AI Agent 可从返回值的 context 中获取已解析的参数，用于后续调用
"""

import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from typing import Any, Literal, Optional, List, Union

from dbw_client import DBWClient
from error_codes import DbwApiError


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

_TICKET_STATUS_MAP = {
    "TicketUndo": "未开始",
    "TicketPreCheck": "预检查中",
    "TicketPreCheckError": "预检查失败",
    "TicketExamine": "审批中",
    "TicketCancel": "已取消",
    "TicketReject": "已拒绝",
    "TicketWaitExecute": "等待执行",
    "TicketExecute": "执行中",
    "TicketFinished": "已完成",
    "TicketError": "执行失败",
}

# .env 文件路径 (skills/.env)
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)

# 各函数不支持的实例类型（"External" 匹配所有 External-* 前缀的实例）
# 注意：instance_type 取自 client.get_instance_type()，与 dbw API ds_type 一致；
# SQL Server 的实际值为 "MSSQL"（不是 "SQLServer"）。
_UNSUPPORTED: dict[str, set[str]] = {
    "list_databases": {"Redis"},
    "list_tables": {"Redis"},
    "get_table_info": {"Mongo", "Redis"},
    "nl2sql": {"Redis"},
    "query_sql": {"Mongo", "Redis"},
    "describe_slow_logs": {"MSSQL", "Redis", "External"},
    "describe_aggregate_slow_logs": {"MSSQL", "Redis", "External"},
    "describe_slow_log_time_series_stats": {"MSSQL", "Redis", "External"},
    "describe_full_sql_detail": {"MSSQL", "Mongo", "Redis", "External"},
    "describe_deadlock": {"Postgres", "MSSQL", "Mongo", "Redis", "External"},
    "describe_trx_and_locks": {"MSSQL", "Mongo", "Redis", "External"},
    "describe_lock_wait": {"MSSQL", "Mongo", "Redis", "External"},
    "create_trx_export_task": {"MSSQL", "Mongo", "Redis", "External"},
    "describe_err_logs": {"MSSQL", "Mongo", "Redis", "External"},
    "describe_table_space": {"MSSQL", "Mongo", "Redis", "External"},
    "describe_table_spaces": {"MSSQL", "Mongo", "Redis", "External"},
    "describe_health_summary": {"MSSQL", "Mongo", "Redis", "External"},
    "describe_instance_nodes": {"MSSQL", "Redis", "External"},
    "get_metric_items": {"VeDBMySQL", "Postgres", "MSSQL", "Mongo", "Redis", "External"},
    "get_metric_data": {"VeDBMySQL", "Postgres", "MSSQL", "Mongo", "Redis", "External"},
    "describe_table_metric": {"MSSQL", "Mongo", "Redis", "External"},
    "list_connections": {"MSSQL", "Redis", "External"},
    "list_history_connections": {"MSSQL", "Redis", "External"},
    "create_dml_sql_change_ticket": {"MSSQL", "Mongo", "Redis", "External"},
    "create_ddl_sql_change_ticket": {"MSSQL", "Mongo", "Redis", "External"},
}

_TYPE_DISPLAY = {
    "MySQL": "MySQL", "VeDBMySQL": "VeDB-MySQL", "Postgres": "PostgreSQL",
    "MSSQL": "SQL Server", "Mongo": "MongoDB", "Redis": "Redis", "External": "External",
}


def _check_supported(func_name: str, instance_type: str, ctx: Optional[dict] = None) -> Optional[dict]:
    """检查函数是否支持当前实例类型。不支持时返回错误字典，支持时返回 None。"""
    blocked = _UNSUPPORTED.get(func_name)
    if not blocked:
        return None
    check_type = "External" if instance_type.startswith("External") else instance_type
    if check_type not in blocked:
        return None
    display = _TYPE_DISPLAY.get(check_type, check_type)
    return _error(f"{func_name} 不支持 {display} 类型实例", context=ctx)


# ──────────────────────────────────────────────
# 结果封装
# ──────────────────────────────────────────────

def _ok(data: Any = None, message: str = "成功", context: Optional[dict] = None) -> dict[str, Any]:
    result = {"success": True, "message": message}
    if context:
        result["context"] = context
    if data is not None:
        result["data"] = data
    return result


def _error(message: str, error_detail: Any = None, context: Optional[dict] = None) -> dict[str, Any]:
    result = {"success": False, "message": message}
    if context:
        result["context"] = context
    if error_detail:
        result["error"] = error_detail
    return result


def _sql_failed(reason_detail: Optional[str], state: str, context: Optional[dict] = None) -> dict[str, Any]:
    """execute_sql 的 state=Failed 分支：原样返回 reason_detail，由 agent 解读原始错误。"""
    return _error(
        reason_detail or "SQL执行失败",
        {"state": state, "reason_detail": reason_detail},
        context=context,
    )


def _validate_time_range(start_time: int, end_time: int, max_span_days: int = 30) -> Optional[dict[str, Any]]:
    """校验 start_time/end_time 合法性（客户端侧，让存量版本也能拦参数）。

    与业界云厂商慢日志接口保持一致采用 30 天上限（dbw-mgr 服务端新版本是 31 天，
    客户端更严 1 天留端到端缓冲，避免时区/数据延迟导致的 31 天边缘失败）。
    """
    if not start_time or not end_time:
        return _error("start_time 和 end_time 不能为空")
    if start_time >= end_time:
        return _error("start_time 必须小于 end_time")
    if end_time - start_time > max_span_days * 24 * 3600:
        return _error(f"时间范围不能超过 {max_span_days} 天")
    return None


def _validate_pagination(page_number: int, page_size: int) -> Optional[dict[str, Any]]:
    """校验分页参数（客户端侧，dbw-mgr MR 5292 前服务端不做校验）。"""
    if page_number < 1:
        return _error("page_number 必须 ≥ 1")
    if page_size < 1 or page_size > 100:
        return _error("page_size 必须在 1~100 之间")
    return None


def _wrap_exception(func_label: str, exc: Exception, context: Optional[dict] = None) -> dict[str, Any]:
    """把上游异常（尤其是 DbwApiError）转成结构化错误字典。"""
    if isinstance(exc, DbwApiError):
        detail: dict[str, Any] = {"code": exc.code}
        if exc.code_n is not None:
            detail["code_n"] = exc.code_n
        if exc.request_id:
            detail["request_id"] = exc.request_id
        if exc.message:
            detail["raw_message"] = exc.message
        if exc.hint:
            detail["hint"] = exc.hint
        if exc.subtype:
            detail["subtype"] = exc.subtype
        return _error(f"{func_label}失败: {exc}", detail, context=context)
    return _error(f"{func_label}失败: {exc}", context=context)


def _to_result(data: Any, message: str = "操作成功", context: Optional[dict] = None) -> dict[str, Any]:
    if data is None:
        return _error("返回数据为空", context=context)
    if isinstance(data, dict):
        if "error" in data or "Error" in data:
            error_info = data.get("error") or data.get("Error")
            return _error(f"API错误: {error_info}", data, context=context)
        return _ok(data, message, context=context)
    return _ok(data, message, context=context)


def _build_context(
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    instance_type: Optional[str] = None,
    region: Optional[str] = None,
) -> dict:
    """构建 context 快照（只含 Agent 可见字段）"""
    ctx = {}
    if instance_id:
        ctx["instance_id"] = instance_id
    if database:
        ctx["database"] = database
    if instance_type:
        ctx["instance_type"] = instance_type
    if region:
        ctx["region"] = region
    return ctx


def _truncate_list(data: dict, *, limit: int = 50, label: str = "data") -> dict:
    """对列表做统一截断 + 写文件降级，防止撑爆 Agent 上下文。

    data: dict {key: list} — 所有列表按同一 limit 截断。
    返回 dict: truncated, returned_count, artifact_path + 各 key 的截断后列表。
    写文件失败 → 不截断，全量返回。
    """
    max_len = max((len(v) for v in data.values() if isinstance(v, list)), default=0)
    if max_len <= limit:
        return {"truncated": False, "returned_count": max_len, "artifact_path": None, **data}

    artifact_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            prefix=f"{label}_", suffix=".json", dir="/tmp", delete=False, mode="w")
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.close()
        artifact_path = tmp.name
    except Exception:
        pass

    if artifact_path is None:
        return {"truncated": False, "returned_count": max_len, "artifact_path": None, **data}

    return {
        "truncated": True,
        "returned_count": limit,
        "artifact_path": artifact_path,
        **{k: (v[:limit] if isinstance(v, list) else v) for k, v in data.items()},
    }


# ──────────────────────────────────────────────
# 数据归约工具
# ──────────────────────────────────────────────

def _dump_artifact(data: Any, *, label: str, description: str = "") -> Optional[str]:
    """将大数据写入临时 JSON 文件，返回文件路径。写入失败返回 None。

    文件头部带 _artifact_meta 描述数据结构，便于后续读取时快速了解内容。
    """
    import datetime
    meta = {
        "_artifact_meta": {
            "label": label,
            "description": description,
            "created_at": datetime.datetime.now().isoformat(),
        },
        "data": data,
    }
    try:
        tmp = tempfile.NamedTemporaryFile(
            prefix=f"dbw_{label}_", suffix=".json", dir="/tmp", delete=False, mode="w")
        json.dump(meta, tmp, ensure_ascii=False, indent=2, default=str)
        tmp.close()
        return tmp.name
    except Exception:
        return None


def _compute_connection_stats(sessions: list[dict]) -> dict:
    """从原始 session 列表计算多维度统计摘要。纯数学运算，不含判断逻辑。

    时间分桶边界：0-10s / 10-60s / 1-5min / 5-60min / >1h。
    """
    from collections import Counter, defaultdict

    total = len(sessions)
    if total == 0:
        return {"total": 0, "sleep_count": 0, "sleep_ratio": 0.0,
                "active_count": 0, "active_ratio": 0.0,
                "by_command": {}, "by_user_top10": [], "by_db_top10": [],
                "by_ip_top10": [], "by_time_bucket": {},
                "user_count": 0, "ip_count": 0}

    # by command
    cmd_counter = Counter(s.get("command", "") for s in sessions)
    sleep_count = cmd_counter.get("Sleep", 0)
    active_count = total - sleep_count

    # by user — count + avg_time
    user_stats = defaultdict(lambda: {"count": 0, "total_time": 0})
    for s in sessions:
        user = s.get("user", "")
        user_stats[user]["count"] += 1
        user_stats[user]["total_time"] += int(s.get("time", 0))

    by_user_top10 = []
    for user, st in sorted(user_stats.items(), key=lambda x: -x[1]["count"])[:10]:
        avg_time = st["total_time"] / st["count"] if st["count"] else 0
        by_user_top10.append({
            "user": user, "count": st["count"],
            "ratio": round(st["count"] / total, 3),
            "avg_time": round(avg_time, 1),
        })

    # by db
    db_counter = Counter(s.get("db") or "(none)" for s in sessions)
    by_db_top10 = [{"db": db, "count": cnt, "ratio": round(cnt / total, 3)}
                   for db, cnt in db_counter.most_common(10)]

    # by ip
    def _extract_ip(host: str) -> str:
        return host.split(":")[0] if host else ""
    ip_counter = Counter(_extract_ip(s.get("host", "")) for s in sessions)
    by_ip_top10 = [{"ip": ip, "count": cnt, "ratio": round(cnt / total, 3)}
                   for ip, cnt in ip_counter.most_common(10)]

    # by time bucket
    buckets = {"0-10s": 0, "10-60s": 0, "1-5min": 0, "5-60min": 0, ">1h": 0}
    sleep_times = []
    for s in sessions:
        t = int(s.get("time", 0))
        if t <= 10:
            buckets["0-10s"] += 1
        elif t <= 60:
            buckets["10-60s"] += 1
        elif t <= 300:
            buckets["1-5min"] += 1
        elif t <= 3600:
            buckets["5-60min"] += 1
        else:
            buckets[">1h"] += 1
        if s.get("command") == "Sleep":
            sleep_times.append(t)

    avg_sleep_time = round(sum(sleep_times) / len(sleep_times), 1) if sleep_times else 0.0

    return {
        "total": total,
        "by_command": dict(cmd_counter.most_common()),
        "sleep_count": sleep_count,
        "sleep_ratio": round(sleep_count / total, 3),
        "active_count": active_count,
        "active_ratio": round(active_count / total, 3),
        "avg_sleep_time": avg_sleep_time,
        "by_user_top10": by_user_top10,
        "by_db_top10": by_db_top10,
        "by_ip_top10": by_ip_top10,
        "by_time_bucket": buckets,
        "user_count": len(user_stats),
        "ip_count": len(ip_counter),
    }


# ──────────────────────────────────────────────
# 数据处理工具
# ──────────────────────────────────────────────

def _decode_cell(value: str) -> str:
    """解码 Go 字节数组格式的 cell 值，如 '[105 110 102 111]' -> 'info'"""
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if inner and all(part.isdigit() for part in inner.split()):
            try:
                return bytes(int(b) for b in inner.split()).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                pass
    return value


def _normalize_rows(columns: list, rows: list) -> list:
    """将 Cells 格式的行数据转换为 {column: value} 字典列表"""
    normalized = []
    for row in rows:
        cells = row.get("Cells") or row.get("cells") if isinstance(row, dict) else None
        if cells and isinstance(cells, list):
            decoded = [_decode_cell(c) for c in cells]
            normalized.append(dict(zip(columns, decoded)) if columns else decoded)
        else:
            normalized.append(row)
    return normalized


def _ticket_url(ticket_id: str, instance_type: str, region: str = "cn-beijing") -> str:
    return f"https://console.volcengine.com/dbw/region:dbw+{region}/ticket/detail?ticketId={ticket_id}&dsType={instance_type}"


def _status_text(status: str) -> str:
    return _TICKET_STATUS_MAP.get(status, status)


# ──────────────────────────────────────────────
# Client
# ��─────────────────────────────────────────────

class ToolboxClient:
    """封装 DBWClient，增加 instance_type 缓存和默认参数。"""

    def __init__(self, dbw: DBWClient, instance_id: Optional[str] = None, database: Optional[str] = None):
        self.dbw = dbw
        self.instance_id = instance_id
        self.database = database
        self.region = dbw.region
        self._instance_type_cache: dict[str, str] = {}

    def get_instance_type(self, instance_id: str) -> str:
        """通过 instance_id 自动查询并缓存实例类型。"""
        if instance_id in self._instance_type_cache:
            return self._instance_type_cache[instance_id]
        # 先按 ID 查
        result = self.dbw.describe_instances({
            "InstanceId": instance_id, "PageSize": 1, "InstancesVersion": "v2",
        })
        if isinstance(result, dict):
            instances = result.get("instances", [])
            if instances:
                t = instances[0].get("instance_type", "")
                self._instance_type_cache[instance_id] = t
                return t
        # 兜底按名称查
        result = self.dbw.describe_instances({
            "InstanceName": instance_id, "PageSize": 1, "InstancesVersion": "v2",
        })
        if isinstance(result, dict):
            instances = result.get("instances", [])
            if instances:
                t = instances[0].get("instance_type", "")
                self._instance_type_cache[instance_id] = t
                return t
        raise ValueError(f"无法通过 '{instance_id}' 查询到实例（按 ID 和名称均未找到），请检查是否正确")


def create_client(
    region: Optional[str] = None,
    ak: Optional[str] = None,
    sk: Optional[str] = None,
    host: Optional[str] = None,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
) -> ToolboxClient:
    """创建 ToolboxClient，自动从环境变量 / .env 文件加载凭证。

    Args:
        region: 区域（RegionId），默认从 VOLCENGINE_REGION 读取
        ak: Access Key，默认从 VOLCENGINE_ACCESS_KEY 读取
        sk: Secret Key，默认从 VOLCENGINE_SECRET_KEY 读取
        instance_id: 默认实例 ID，默认从 VOLCENGINE_INSTANCE_ID 读取
        database: 默认数据库名，默认从 VOLCENGINE_DATABASE 读取
    """
    dbw = DBWClient(
        region=region or os.getenv("VOLCENGINE_REGION"),
        ak=ak or os.getenv("VOLCENGINE_ACCESS_KEY"),
        sk=sk or os.getenv("VOLCENGINE_SECRET_KEY"),
        host=host or os.getenv("VOLCENGINE_ENDPOINT"),
        instance_id=instance_id or os.getenv("VOLCENGINE_INSTANCE_ID"),
        database=database or os.getenv("VOLCENGINE_DATABASE"),
    )
    return ToolboxClient(
        dbw=dbw,
        instance_id=instance_id or os.getenv("VOLCENGINE_INSTANCE_ID") or dbw.instance_id,
        database=database or os.getenv("VOLCENGINE_DATABASE") or dbw.database,
    )


# ──────────────────────────────────────────────
# 参数自动补全
# ──────────────────────────────────────────────

def _prepare(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
) -> dict[str, Any]:
    """参数补全：解析 instance_id → instance_type，补全 database。

    返回:
        成功: {"ok": True, "params": {"instance_id", "instance_type", "database", "region"}, "ctx": dict}
        失败: {"ok": False, "error": dict}
    """
    # 1. 解析 instance_id
    _instance_id = instance_id or client.instance_id
    if not _instance_id:
        ctx = _build_context(database=database, region=client.region)
        return {"ok": False, "error": _error(
            "缺少 instance_id，请先调用 list_instances() 查询可用实例",
            {"missing": ["instance_id"]}, context=ctx,
        )}

    # 2. 自动解析 instance_type
    try:
        _instance_type = client.get_instance_type(_instance_id)
    except ValueError as e:
        ctx = _build_context(instance_id=_instance_id, database=database, region=client.region)
        return {"ok": False, "error": _error(str(e), context=ctx)}

    # 3. 补全 database
    # 仅当 instance_id 与默认一致时才回退到默认 database，
    # 避免 Redis 等不同类型实例错误继承环境变量中的 database
    if database:
        _database = database
    elif not instance_id or instance_id == client.instance_id:
        _database = client.database
    else:
        _database = None

    # 4. 构建 context
    ctx = _build_context(
        instance_id=_instance_id,
        database=_database,
        instance_type=_instance_type,
        region=client.region,
    )

    return {
        "ok": True,
        "params": {
            "instance_id": _instance_id,
            "instance_type": _instance_type,
            "database": _database,
            "region": client.region,
        },
        "ctx": ctx,
    }


# ──────────────────────────────────────────────
# 环境管理（不需要 client）
# ──────────────────────────────────────────────

def check_env() -> dict[str, Any]:
    """检查当前凭证配置状态（不泄露实际值）。"""
    all_keys = [
        "VOLCENGINE_ACCESS_KEY", "VOLCENGINE_SECRET_KEY", "VOLCENGINE_REGION",
        "VOLCENGINE_INSTANCE_ID", "VOLCENGINE_DATABASE",
    ]
    env_exists = os.path.exists(_ENV_PATH)
    file_vars: dict[str, str] = {}
    if env_exists:
        try:
            file_vars = DBWClient._parse_env_file(_ENV_PATH)
        except Exception:
            pass

    configured = []
    missing = []
    for key in all_keys:
        if os.environ.get(key) or file_vars.get(key):
            configured.append(key)
        else:
            missing.append(key)

    # APIG 凭证由平台自动注入，不需要用户配置
    apig_ok = bool(os.environ.get("ARK_SKILL_API_BASE") and os.environ.get("ARK_SKILL_API_KEY"))
    aksk_ok = all(k in configured for k in ("VOLCENGINE_ACCESS_KEY", "VOLCENGINE_SECRET_KEY"))
    required_ok = apig_ok or aksk_ok

    return _ok(
        data={
            "env_path": _ENV_PATH,
            "env_file_exists": env_exists,
            "configured_keys": configured,
            "missing_keys": missing,
            "credentials_ready": required_ok,
        },
        message="凭证已就绪" if required_ok else "缺少必要配置，请提供 AK/SK",
    )


def update_env(**kwargs: str) -> dict[str, Any]:
    """安全地更新 .env 文件中的配置项。仅修改 VOLCENGINE_ 前缀的 key。"""
    allowed_keys = {
        "VOLCENGINE_ACCESS_KEY", "VOLCENGINE_SECRET_KEY", "VOLCENGINE_REGION",
        "VOLCENGINE_INSTANCE_ID", "VOLCENGINE_DATABASE",
    }
    to_update = {k: v for k, v in kwargs.items() if k in allowed_keys and v}
    ignored = [k for k in kwargs if k not in allowed_keys]

    if not to_update:
        return _error("没有可更新的有效配置项", {"ignored": ignored})

    existing_lines: list[str] = []
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, "r") as f:
            existing_lines = f.readlines()

    def _extract_key(line: str) -> Optional[str]:
        s = line.strip()
        if not s or s.startswith("#"):
            return None
        raw = s[7:] if s.startswith("export ") else s
        if "=" not in raw:
            return None
        return raw.partition("=")[0].strip()

    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in existing_lines:
        key = _extract_key(line)
        if key and key in to_update:
            prefix = "export " if line.strip().startswith("export ") else ""
            new_lines.append(f'{prefix}{key}="{to_update[key]}"\n')
            updated_keys.add(key)
        else:
            new_lines.append(line)

    for key, value in to_update.items():
        if key not in updated_keys:
            new_lines.append(f'export {key}="{value}"\n')
            updated_keys.add(key)

    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"

    tmp_path = _ENV_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        f.writelines(new_lines)
    os.replace(tmp_path, _ENV_PATH)

    return _ok(
        data={"updated": sorted(updated_keys), "ignored": ignored},
        message=f"已更新 {len(updated_keys)} 项配置",
    )


# ──────────────────────────────────────────────
# 公开函数：数据查询与分析
# ──────────────────────────────────────────────

def nl2sql(
    client: ToolboxClient,
    query: str,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    tables: Optional[List[str]] = None,
) -> dict[str, Any]:
    """自然语言转 SQL（生成但不执行）。"""
    try:
        if not query:
            return _error("query 参数不能为空")
        prep = _prepare(client, instance_id=instance_id, database=database)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]
        unsupported = _check_supported("nl2sql", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        if not p["database"]:
            return _error("缺少 database 参数", {"missing": ["database"]}, context=ctx)

        req = {
            "instance_id": p["instance_id"],
            "instance_type": p["instance_type"],
            "database": p["database"],
            "query": query,
        }
        if tables:
            req["tables"] = tables

        result = client.dbw.nl2sql(req)
        return _to_result(result, "SQL生成成功", context=ctx)
    except Exception as e:

        return _wrap_exception("nl2sql", e)


def execute_sql(
    client: ToolboxClient,
    sql: str,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
) -> dict[str, Any]:
    """执行 SQL 查询（仅支持 SELECT/SHOW/EXPLAIN 等只读操作）。

    ⚠️ 单次最多返回 3000 行，超出部分静默截断。返回恰好 3000 行 = 数据被截断。
    """
    try:
        if not sql:
            return _error("sql 参数不能为空")
        prep = _prepare(client, instance_id=instance_id, database=database)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        if not p["database"]:
            return _error("缺少 database 参数", {"missing": ["database"]}, context=ctx)

        req = {
            "instance_id": p["instance_id"],
            "instance_type": p["instance_type"],
            "database": p["database"],
            "commands": sql,
            "time_out_seconds": 60,
        }

        result = client.dbw.execute_sql(req)

        if isinstance(result, dict):
            # 适配 PascalCase 返回
            if "Results" in result and isinstance(result["Results"], list) and result["Results"]:
                first = result["Results"][0]
                state = first.get("State", "")
                if state == "Success":
                    columns = first.get("ColumnNames") or []
                    rows = first.get("Rows") or []
                    return _ok({
                        "sql": first.get("CommandStr", sql),
                        "state": state,
                        "row_count": first.get("RowCount", 0),
                        "columns": columns,
                        "rows": _normalize_rows(columns, rows),
                    }, "查询成功", context=ctx)
                else:
                    return _sql_failed(first.get("ReasonDetail"), state, ctx)

            # 适配 snake_case 返回
            if "results" in result and isinstance(result["results"], list) and result["results"]:
                first = result["results"][0]
                state = first.get("state", "")
                if state == "Success":
                    columns = first.get("column_names", [])
                    rows = first.get("rows", [])
                    return _ok({
                        "sql": first.get("command_str", sql),
                        "state": state,
                        "row_count": first.get("row_count", 0),
                        "columns": columns,
                        "rows": _normalize_rows(columns, rows),
                    }, "查询成功", context=ctx)
                else:
                    return _sql_failed(first.get("reason_detail"), state, ctx)

            # 旧格式兜底
            state = result.get("state", "")
            if state == "success":
                columns = result.get("column_names", [])
                rows = result.get("rows", [])
                return _ok({
                    "sql": result.get("command_str", sql),
                    "state": state,
                    "row_count": result.get("row_count", 0),
                    "columns": columns,
                    "rows": _normalize_rows(columns, rows),
                }, "查询成功", context=ctx)
            else:
                return _sql_failed(result.get("reason_detail"), state, ctx)
        return _to_result(result, "执行完成", context=ctx)
    except Exception as e:
        return _wrap_exception("execute_sql", e)


def query_sql(
    client: ToolboxClient,
    sql: str,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
):
    """执行 SELECT/SHOW 查询并返回 pandas DataFrame。"""
    try:
        import pandas as pd
    except ImportError:
        return _error("query_sql 需要 pandas 库，请先执行: pip install pandas")

    # query_sql 不支持 MongoDB / Redis（无法转为 DataFrame）
    prep = _prepare(client, instance_id=instance_id, database=database)
    if not prep["ok"]:
        return prep["error"]
    unsupported = _check_supported("query_sql", prep["params"]["instance_type"], prep["ctx"])
    if unsupported:
        return unsupported

    result = execute_sql(client, sql=sql, instance_id=instance_id, database=database)
    if not result.get("success"):
        return result

    data = result.get("data") or {}
    columns = data.get("columns") or []
    rows = data.get("rows") or []
    records = [row["Cells"] for row in rows if isinstance(row, dict) and "Cells" in row]
    if not records:
        records = [list(row.values()) for row in rows if isinstance(row, dict)]
    return pd.DataFrame(records, columns=columns)


# ──────────────────────────────────────────────
# 公开函数：元数据
# ──────────────────────────────────────────────

def list_databases(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """列出数据库。"""
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("list_databases", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        result = client.dbw.list_databases({
            "instance_id": p["instance_id"],
            "instance_type": p["instance_type"],
            "page_number": page_number,
            "page_size": page_size,
        })

        if isinstance(result, dict):
            items = result.get("items") or []
            databases = [{
                "name": item.get("name", ""),
                "charset": item.get("character_set_name", ""),
                "collation": item.get("collation_name", ""),
                "is_system": item.get("is_system_db", False),
                "description": item.get("description", ""),
            } for item in items]
            return _ok({
                "total": result.get("total", 0),
                "page": page_number,
                "databases": databases,
            }, f"共 {len(databases)} 个数据库", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("list_databases", e)


def list_tables(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    schema: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 50,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """列出数据库中的表。fetch_all=True 获取全部表。"""
    try:
        prep = _prepare(client, instance_id=instance_id, database=database)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("list_tables", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        if not p["database"]:
            return _error("缺少 database 参数", {"missing": ["database"]}, context=ctx)

        req = {
            "instance_id": p["instance_id"],
            "instance_type": p["instance_type"],
            "database": p["database"],
            "page_number": page_number,
            "page_size": page_size,
        }
        if schema:
            req["schema"] = schema

        if fetch_all:
            all_tables = []
            req["page_size"] = 50
            req["page_number"] = 1
            while True:
                result = client.dbw.list_tables(req)
                if not isinstance(result, dict):
                    break
                items = result.get("items") or []
                all_tables.extend(items)
                total = result.get("total", 0)
                if len(all_tables) >= total or not items:
                    break
                req["page_number"] += 1
            return _ok({
                "total": len(all_tables),
                "database": p["database"],
                "schema": schema,
                "tables": all_tables,
            }, f"共 {len(all_tables)} 张表", context=ctx)

        result = client.dbw.list_tables(req)
        if isinstance(result, dict):
            return _ok({
                "total": result.get("total", 0),
                "page": page_number,
                "database": p["database"],
                "schema": schema,
                "tables": result.get("items") or [],
            }, f"共 {len(result.get('items') or [])} 张表", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("list_tables", e)


def get_table_info(
    client: ToolboxClient,
    table: str,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    schema: Optional[str] = None,
) -> dict[str, Any]:
    """获取表结构（列名、类型、主键、注释等）。"""
    try:
        if not table:
            return _error("table 参数不能为空")
        prep = _prepare(client, instance_id=instance_id, database=database)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("get_table_info", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        if not p["database"]:
            return _error("缺少 database 参数", {"missing": ["database"]}, context=ctx)

        # Postgres 不支持 GetTableInfo API，走 SQL fallback
        if p["instance_type"] == "Postgres" or p["instance_id"].startswith("External-Postgres"):
            return _pg_get_table_info(client, table, p["instance_id"], p["database"], schema, ctx)

        req = {
            "instance_id": p["instance_id"],
            "instance_type": p["instance_type"],
            "database": p["database"],
            "table": table,
        }
        if schema:
            req["schema"] = schema

        result = client.dbw.get_table_info(req)

        if isinstance(result, dict):
            meta = result.get("table_meta", result)
            columns = [{
                "name": col.get("name", ""),
                "type": col.get("type", ""),
                "length": col.get("length", ""),
                "nullable": col.get("allow_be_null", True),
                "primary_key": col.get("is_primary_key", False),
                "auto_increment": col.get("is_auto_increment", False),
                "default": col.get("default_value"),
                "comment": col.get("comment", ""),
            } for col in meta.get("columns", [])]
            return _ok({
                "name": meta.get("name", table),
                "engine": meta.get("engine", ""),
                "charset": meta.get("character_set", ""),
                "definition": meta.get("definition", ""),
                "columns": columns,
            }, f"表 {table} 结构获取成功", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("get_table_info", e)


def _pg_get_table_info(
    client: ToolboxClient,
    table: str,
    instance_id: str,
    database: str,
    schema: Optional[str],
    ctx: dict,
) -> dict[str, Any]:
    """Postgres 通过 information_schema 查询表结构。"""
    schema = schema or "public"
    sql = (
        f"SELECT column_name, data_type, character_maximum_length, "
        f"is_nullable, column_default, "
        f"col_description((table_schema||'.'||table_name)::regclass, ordinal_position) as comment "
        f"FROM information_schema.columns "
        f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
        f"ORDER BY ordinal_position"
    )
    result = execute_sql(client, sql=sql, instance_id=instance_id, database=database)
    if not result.get("success"):
        return _error(f"PG get_table_info 失败: {result.get('message')}", context=ctx)

    rows = result["data"].get("rows", [])
    columns = [{
        "name": row.get("column_name", ""),
        "type": row.get("data_type", ""),
        "length": row.get("character_maximum_length", ""),
        "nullable": row.get("is_nullable", "YES") == "YES",
        "primary_key": False,
        "auto_increment": False,
        "default": row.get("column_default"),
        "comment": row.get("comment", ""),
    } for row in rows]
    return _ok({
        "name": table,
        "engine": "PostgreSQL",
        "charset": "",
        "definition": "",
        "columns": columns,
    }, f"表 {table} 结构获取成功 (via SQL fallback)", context=ctx)


def list_instances(
    client: ToolboxClient,
    ds_type: Optional[Literal["MySQL", "Postgres", "Mongo", "Redis", "MSSQL", "VeDBMySQL", "External"]] = None,
    instance_name: Optional[str] = None,
    instance_id: Optional[str] = None,
    instance_status: Optional[str] = None,
    query: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """查询数据源列表（数据库实例）。须传过滤项（instance_name/instance_id/ds_type/query），查全量无意义。"""
    try:
        ctx = _build_context(region=client.region)
        args = {
            "PageNumber": page_number,
            "PageSize": page_size,
            "OrderBy": "CreateTime",
            "SortBy": "DESC",
            "InstancesVersion": "v2",
        }
        if ds_type:
            args["DSType"] = ds_type
        if instance_name:
            args["InstanceName"] = instance_name
        if instance_id:
            args["InstanceId"] = instance_id
        if instance_status:
            args["InstanceStatus"] = instance_status
        if query:
            args["Query"] = query

        result = client.dbw.describe_instances(args)

        if isinstance(result, dict):
            instances = result.get("instances", [])
            normalized = []
            for inst in instances:
                spec = inst.get("instance_spec", {})
                item = {
                    "id": inst.get("instance_id", ""),
                    "name": inst.get("instance_name", ""),
                    "status": inst.get("instance_status", ""),
                    "type": inst.get("instance_type", ""),
                    "version": inst.get("db_engine_version", ""),
                    "region": inst.get("region_id", ""),
                    "zone": inst.get("zone", ""),
                    "create_time": inst.get("create_time", ""),
                }
                # 托管实例才有连接信息和规格；External 实例由 DBW 代理连接
                if inst.get("instance_type") != "External":
                    item.update({
                        "endpoint": inst.get("internal_address", ""),
                        "port": inst.get("port", 3306),
                        "cpu": spec.get("cpu_num", 0),
                        "memory": spec.get("mem_in_gi_b", 0),
                        "storage": spec.get("storage", 0),
                    })
                normalized.append(item)
            total = result.get("total", 0)
            return _ok({
                "total": total,
                "page_number": page_number,
                "page_size": page_size,
                "instances": normalized,
            }, f"共 {total} 个实例，当前第 {page_number} 页（{len(normalized)} 条）", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("describe_instances", e)


# ──────────────────────────────────────────────
# 公开函数：工单
# ──────────────────────────────────────────────

def create_dml_sql_change_ticket(
    client: ToolboxClient,
    sql_text: str,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    title: Optional[str] = None,
    memo: Optional[str] = None,
) -> dict[str, Any]:
    """创建 DML 工单（数据变更）。执行方式固定为 Manual（审批后由用户手动触发）。"""
    try:
        if not sql_text:
            return _error("sql_text 参数不能为空")
        prep = _prepare(client, instance_id=instance_id, database=database)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("create_dml_sql_change_ticket", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        if not p["database"]:
            return _error("缺少 database 参数", {"missing": ["database"]}, context=ctx)

        req = {
            "instance_id": p["instance_id"],
            "instance_type": p["instance_type"],
            "database_name": p["database"],
            "sql_text": sql_text,
            "ticket_execute_type": "Manual",
        }
        if title:
            req["title"] = title
        if memo:
            req["memo"] = memo

        result = client.dbw.create_dml_sql_change_ticket(req)

        if isinstance(result, dict):
            ticket_id = result.get("ticket_id", "")
            status = result.get("ticket_status", "")
            return _ok({
                "ticket_id": ticket_id,
                "status": status,
                "status_text": _status_text(status),
                "approver": result.get("current_user", {}),
                "ticket_url": _ticket_url(ticket_id, p["instance_type"], p["region"]),
                "sql": sql_text,
                "database": p["database"],
            }, f"工单 {ticket_id} 创建成功，状态: {_status_text(status)}", context=ctx)

        return _to_result(result, "工单创建成功", context=ctx)
    except Exception as e:
        return _wrap_exception("create_dml_sql_change_ticket", e)


def create_ddl_sql_change_ticket(
    client: ToolboxClient,
    sql_text: str,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    title: Optional[str] = None,
    memo: Optional[str] = None,
) -> dict[str, Any]:
    """创建 DDL 工单（结构变更）。执行方式固定为 Manual（审批后由用户手动触发）。"""
    try:
        if not sql_text:
            return _error("sql_text 参数不能为空")
        prep = _prepare(client, instance_id=instance_id, database=database)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("create_ddl_sql_change_ticket", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        if not p["database"]:
            return _error("缺少 database 参数", {"missing": ["database"]}, context=ctx)

        req = {
            "instance_id": p["instance_id"],
            "instance_type": p["instance_type"],
            "database_name": p["database"],
            "sql_text": sql_text,
            "ticket_execute_type": "Manual",
        }
        if title:
            req["title"] = title
        if memo:
            req["memo"] = memo

        result = client.dbw.create_ddl_sql_change_ticket(req)

        if isinstance(result, dict):
            ticket_id = result.get("ticket_id", "")
            status = result.get("ticket_status", "")
            return _ok({
                "ticket_id": ticket_id,
                "status": status,
                "status_text": _status_text(status),
                "approver": result.get("current_user", {}),
                "ticket_url": _ticket_url(ticket_id, p["instance_type"], p["region"]),
                "sql": sql_text,
                "database": p["database"],
            }, f"DDL工单 {ticket_id} 创建成功，状态: {_status_text(status)}", context=ctx)

        return _to_result(result, "工单创建成功", context=ctx)
    except Exception as e:
        return _wrap_exception("create_ddl_sql_change_ticket", e)


def describe_tickets(
    client: ToolboxClient,
    list_type: str,
    order_by: Optional[str] = None,
    sort_by: str = "ASC",
    page_number: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """查询工单列表。list_type: All | CreatedByMe | ApprovedByMe"""
    try:
        if not list_type:
            return _error("list_type 参数不能为空")

        req = {
            "list_type": list_type,
            "sort_by": sort_by,
            "page_number": page_number,
            "page_size": page_size,
        }
        if order_by:
            req["order_by"] = order_by

        result = client.dbw.describe_tickets(req)

        if isinstance(result, dict):
            tickets = result.get("tickets", [])
            normalized = []
            for t in tickets:
                ticket_id = t.get("ticket_id", "")
                status = t.get("ticket_status", "")
                normalized.append({
                    "id": ticket_id,
                    "title": t.get("title", ""),
                    "status": status,
                    "status_text": _status_text(status),
                    "type": "DML" if "dml" in ticket_id.lower() else "DDL",
                    "create_time": t.get("create_time", ""),
                    "creator": t.get("create_user", {}),
                    "approver": t.get("current_user", {}),
                    "url": _ticket_url(ticket_id, t.get("instance_type", ""), client.region),
                })
            return _ok({
                "total": result.get("total", 0),
                "tickets": normalized,
            }, f"共 {len(normalized)} 个工单")

        return _to_result(result)
    except Exception as e:
        return _wrap_exception("describe_tickets", e)


def describe_ticket_detail(client: ToolboxClient, ticket_id: str) -> dict[str, Any]:
    """查询工单详情。"""
    try:
        if not ticket_id:
            return _error("ticket_id 参数不能为空")

        result = client.dbw.describe_ticket_detail({"ticket_id": ticket_id})

        if isinstance(result, dict):
            status = result.get("ticket_status", "")
            return _ok({
                "id": ticket_id,
                "title": result.get("title", ""),
                "memo": result.get("memo", ""),
                "status": status,
                "status_text": _status_text(status),
                "sql": result.get("sql_text", ""),
                "result": result.get("description", ""),
                "create_time": result.get("create_time", ""),
                "update_time": result.get("update_time", ""),
                "creator": result.get("create_user", {}),
                "approver": result.get("current_user", {}),
                "url": _ticket_url(ticket_id, result.get("instance_type", ""), client.region),
            }, f"工单 {ticket_id} 详情获取成功")

        return _to_result(result)
    except Exception as e:
        return _wrap_exception("describe_ticket_detail", e)


def describe_workflow(client: ToolboxClient, ticket_id: str) -> dict[str, Any]:
    """查询审批流程。"""
    try:
        if not ticket_id:
            return _error("ticket_id 参数不能为空")

        result = client.dbw.describe_workflow({"ticket_id": ticket_id})

        if isinstance(result, dict):
            nodes = []
            for node in result.get("flow_nodes", []):
                status = node.get("status", "")
                nodes.append({
                    "name": node.get("node_name", ""),
                    "approver": node.get("operator", ""),
                    "status": status,
                    "status_text": (
                        "已通过" if status == "Pass"
                        else "审批中" if status == "Approval"
                        else "已拒绝" if status == "Reject"
                        else "未开始"
                    ),
                })
            return _ok({"ticket_id": ticket_id, "nodes": nodes}, f"共 {len(nodes)} 个审批节点")

        return _to_result(result)
    except Exception as e:
        return _wrap_exception("describe_workflow", e)


# ──────────────────────────────────────────────
# 公开函数：慢查询诊断
# ──────────────────────────────────────────────

def describe_slow_logs(
    client: ToolboxClient,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 10,
    order_by: str = "QueryTime",
    sort_by: str = "DESC",
    users: Optional[list[str]] = None,
    source_ips: Optional[list[str]] = None,
    min_query_time: Optional[float] = None,
    max_query_time: Optional[float] = None,
    node_id: Optional[str] = None,
) -> dict[str, Any]:
    """查询慢查询日志明细。start_time/end_time 为 Unix 时间戳（秒）。
    database: 按数据库名过滤。

    客户端侧校验（让存量版本服务端不做校验时也能拿到友好报错）：
    start_time 必填且 end_time > start_time；时间跨度 ≤ 30 天；
    page_number ≥ 1；1 ≤ page_size ≤ 100。
    """
    try:
        err = _validate_time_range(start_time, end_time) or _validate_pagination(page_number, page_size)
        if err:
            return err
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_slow_logs", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        search_param: dict[str, Any] = {}
        if database:
            search_param["DBs"] = [database]
        if users:
            search_param["Users"] = users
        if source_ips:
            search_param["SourceIPs"] = source_ips
        if min_query_time is not None:
            search_param["MinQueryTime"] = min_query_time
        if max_query_time is not None:
            search_param["MaxQueryTime"] = max_query_time

        args = {
            "instance_id": p["instance_id"],
            "DSType": p["instance_type"],
            "start_time": start_time,
            "end_time": end_time,
            "page_number": page_number,
            "page_size": page_size,
            "order_by": order_by,
            "sort_by": sort_by,
            "region_id": p["region"],
        }
        if node_id:
            args["node_id"] = node_id
        if search_param:
            args["search_param"] = search_param

        result = client.dbw.describe_slow_logs(args)

        if isinstance(result, dict):
            logs = [{
                "sql": log.get("sql_text", ""),
                "template": log.get("sql_template", ""),
                "query_time": log.get("query_time", 0),
                "lock_time": log.get("lock_time", 0),
                "rows_scanned": log.get("rows_examined", 0),
                "rows_sent": log.get("rows_sent", 0),
                "timestamp": log.get("timestamp", 0),
                "user": log.get("user", ""),
                "ip": log.get("source_ip", ""),
                "database": log.get("db", ""),
            } for log in result.get("slow_logs", [])]
            total = result.get("total", 0)
            returned_count = len(logs)
            return _ok({
                "total": total,
                "page_number": page_number,
                "page_size": page_size,
                "returned_count": returned_count,
                "logs": logs,
            }, f"返回 {returned_count}/{total} 条慢查询（第 {page_number} 页，每页 {page_size} 条）", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("describe_slow_logs", e)


def describe_aggregate_slow_logs(
    client: ToolboxClient,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 10,
    order_by: str = "TotalQueryTime",
    sort_by: str = "DESC",
    users: Optional[list[str]] = None,
    source_ips: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    tables: Optional[list[str]] = None,
    min_query_time: Optional[float] = None,
    max_query_time: Optional[float] = None,
    node_id: Optional[str] = None,
) -> dict[str, Any]:
    """查询慢查询聚合统计（推荐首选）。
    database: 按数据库名过滤；keywords: SQL 关键词过滤；tables: 按表名过滤。

    客户端校验：时间跨度 ≤ 30 天；page_number ≥ 1；1 ≤ page_size ≤ 100。
    """
    try:
        err = _validate_time_range(start_time, end_time) or _validate_pagination(page_number, page_size)
        if err:
            return err
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_aggregate_slow_logs", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        search_param: dict[str, Any] = {}
        if database:
            search_param["DBs"] = [database]
        if users:
            search_param["Users"] = users
        if source_ips:
            search_param["SourceIPs"] = source_ips
        if keywords:
            search_param["Keywords"] = keywords
        if tables:
            search_param["Tables"] = tables
        if min_query_time is not None:
            search_param["MinQueryTime"] = min_query_time
        if max_query_time is not None:
            search_param["MaxQueryTime"] = max_query_time

        args = {
            "instance_id": p["instance_id"],
            "DSType": p["instance_type"],
            "start_time": start_time,
            "end_time": end_time,
            "page_number": page_number,
            "page_size": page_size,
            "order_by": order_by,
            "sort_by": sort_by,
            "region_id": p["region"],
        }
        if node_id:
            args["node_id"] = node_id
        if search_param:
            args["search_param"] = search_param

        result = client.dbw.describe_aggregate_slow_logs(args)

        if isinstance(result, dict):
            logs = [{
                "sql_template": log.get("sql_template", ""),
                "db": log.get("db", ""),
                "user": log.get("user", ""),
                "source_ip": log.get("source_ip", ""),
                "execute_count": log.get("execute_count", 0),
                "execute_count_ratio": log.get("execute_count_ratio", 0),
                "query_time_ratio": log.get("query_time_ratio", 0),
                "lock_time_ratio": log.get("lock_time_ratio", 0),
                "query_time_stats": log.get("query_time_stats", {}),
                "lock_time_stats": log.get("lock_time_stats", {}),
                "rows_sent_stats": log.get("rows_sent_stats", {}),
                "rows_examined_stats": log.get("rows_examined_stats", {}),
                "first_appear_time": log.get("first_appear_time", 0),
                "last_appear_time": log.get("last_appear_time", 0),
                "sql_fingerprint": log.get("sql_fingerprint", ""),
                "sql_method": log.get("sql_method", ""),
                "table": log.get("table", ""),
            } for log in result.get("aggregate_slow_logs", [])]

            total = result.get("total", 0)
            returned_count = len(logs)
            trunc = _truncate_list({"logs": logs}, limit=50, label="slow_agg")
            data = {
                "total": total,
                "page_number": page_number,
                "page_size": page_size,
                "returned_count": returned_count,
                "truncated": trunc["truncated"],
                "artifact_path": trunc["artifact_path"],
                "logs": trunc["logs"],
            }
            return _ok(data, f"返回 {returned_count}/{total} 条聚合慢查询（第 {page_number} 页，每页 {page_size} 条）", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("describe_aggregate_slow_logs", e)


def describe_slow_log_time_series_stats(
    client: ToolboxClient,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    interval: int = 300,
    min_query_time: Optional[float] = None,
    max_query_time: Optional[float] = None,
    node_id: Optional[str] = None,
) -> dict[str, Any]:
    """查询慢查询时间序列趋势。database: 按数据库名过滤。

    客户端校验：时间跨度 ≤ 30 天。
    """
    try:
        err = _validate_time_range(start_time, end_time)
        if err:
            return err
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_slow_log_time_series_stats", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        search_param: dict[str, Any] = {}
        if database:
            search_param["DBs"] = [database]
        if min_query_time is not None:
            search_param["MinQueryTime"] = min_query_time
        if max_query_time is not None:
            search_param["MaxQueryTime"] = max_query_time

        args = {
            "instance_id": p["instance_id"],
            "DSType": p["instance_type"],
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
        }
        if node_id:
            args["node_id"] = node_id
        if search_param:
            args["search_param"] = search_param

        result = client.dbw.describe_slow_log_time_series_stats(args)

        if isinstance(result, dict):
            return _ok({
                "slow_log_count_stats": result.get("slow_log_count_stats", []),
                "cpu_usage_stats": result.get("cpu_usage_stats", []),
                "interval": result.get("interval", interval),
            }, f"获取 {len(result.get('slow_log_count_stats', []))} 个时间点的慢查询统计", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("describe_slow_log_time_series_stats", e)


def describe_full_sql_detail(
    client: ToolboxClient,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    page_size: int = 50,
    users: Optional[list[str]] = None,
    source_ips: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    tables: Optional[list[str]] = None,
    sql_methods: Optional[list[str]] = None,
    min_exec_time: Optional[int] = None,
    max_exec_time: Optional[int] = None,
    context: Optional[str] = None,
) -> dict[str, Any]:
    """查询完整 SQL 历史详情。支持游标翻页（context 参数）。
    database: 按数据库名过滤。min_exec_time/max_exec_time: 执行时间过滤（毫秒）。
    context: 翻页游标，从上次返回的 data.context 获取。list_over=True 时已无更多数据。"""
    try:
        if not start_time or not end_time:
            return _error("start_time, end_time 不能为空")
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_full_sql_detail", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        search_param: dict[str, Any] = {}
        if database:
            search_param["DBs"] = [database]
        if users:
            search_param["Users"] = users
        if source_ips:
            search_param["SourceIPs"] = source_ips
        if keywords:
            search_param["KeyWords"] = keywords
        if tables:
            search_param["Tables"] = tables
        if sql_methods:
            search_param["SqlMethods"] = sql_methods
        if min_exec_time is not None:
            search_param["DuringDown"] = min_exec_time
        if max_exec_time is not None:
            search_param["DuringUp"] = max_exec_time

        args = {
            "FollowInstanceID": p["instance_id"],
            "instance_type": p["instance_type"],
            "start_time": start_time,
            "end_time": end_time,
            "page_size": page_size,
            "search_param": search_param,
        }
        if context:
            args["context"] = context

        result = client.dbw.describe_full_sql_detail(args)

        if isinstance(result, dict):
            normalized = [{
                "db_name": sql.get("db_name", ""),
                "session_id": sql.get("session_id", ""),
                "sql_type": sql.get("sql_type", ""),
                "query_string": sql.get("query_string", ""),
                "exec_plan": sql.get("exec_plan", []),
                "start_timestamp": sql.get("start_timestamp", ""),
                "end_timestamp": sql.get("end_timestamp", ""),
                "exec_time": sql.get("exec_time", 0),
                "cpu_time": sql.get("cpu_time", 0),
                "row_lock_wait_time": sql.get("rowlock_wait_time", 0),
                "rows_examined": sql.get("rows_examined", 0),
                "rows_sent": sql.get("rows_sent", 0),
                "user_name": sql.get("user_name", ""),
                "client_ip": sql.get("client_ip", ""),
                "sql_fingerprint": sql.get("sql_fingerprint", ""),
                "sql_table": sql.get("sql_table", ""),
                "node_id": sql.get("node_id", ""),
                "sql_template": sql.get("sql_template", ""),
            } for sql in (result.get("describe_full_sql_detail_rows") or [])]
            total = result.get("total", 0)
            returned_count = len(normalized)
            list_over = result.get("list_over", False)
            return _ok({
                "total": total,
                "page_size": page_size,
                "returned_count": returned_count,
                "list_over": list_over,
                "context": result.get("context", ""),
                "sql_list": normalized,
            }, f"返回 {returned_count}/{total} 条 SQL 详情（{'已到末页' if list_over else '可用 context 翻页'}）", context=ctx)

        return _to_result(result, context=ctx)
    except Exception as e:
        return _wrap_exception("describe_full_sql_detail", e)


# ──────────────────────────────────────────────
# 公开函数：健康概览
# ──────────────────────────────────────────────

def describe_health_summary(
    client: ToolboxClient,
    end_time: int,
    instance_id: Optional[str] = None,
    node_ids: Optional[List[str]] = None,
    diag_type: str = "ALL",
) -> dict[str, Any]:
    """查询最近一小时的实例健康概览（CPU、内存、连接数、QPS/TPS 等）。

    end_time 为 Unix 时间戳（秒），返回截止到 end_time 的最近一小时指标。
    diag_type 默认 ALL。未传 node_ids 时自动查询 Primary 节点。
    """
    try:
        if not end_time:
            return _error("end_time 不能为空")
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_health_summary", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        # 未传 node_ids 时自动查询 Primary 节点
        _node_ids = node_ids
        if not _node_ids:
            try:
                nodes = client.dbw.describe_instance_nodes({
                    "DSType": p["instance_type"],
                    "InstanceId": p["instance_id"],
                })
                for n in nodes.get("nodes_info", []):
                    if n.get("node_type") == "Primary":
                        _node_ids = [n["node_id"]]
                        break
                if not _node_ids:
                    all_nodes = nodes.get("nodes_info", [])
                    if all_nodes:
                        _node_ids = [all_nodes[0]["node_id"]]
            except Exception:
                pass  # 部分实例类型不支持查节点，跳过

        req = {
            "InstanceId": p["instance_id"],
            "InstanceType": p["instance_type"],
            "RegionId": p["region"],
            "StartTime": end_time - 300,
            "EndTime": end_time,
            "DiagType": diag_type,
        }
        if _node_ids:
            req["nodeIds"] = _node_ids

        result = client.dbw.describe_health_summary(req)

        if isinstance(result, dict):
            stats_raw = result.get("resource_stats") or []
            metrics = []
            for s in stats_raw:
                if s.get("name") == "慢查询数量":
                    continue
                err_msg = s.get("err_msg") or ""
                if err_msg:
                    continue
                metrics.append({
                    "name": s.get("name", ""),
                    "node_id": s.get("node_id", ""),
                    "avg": s.get("avg"),
                    "max": s.get("max"),
                    "min": s.get("min"),
                    "unit": s.get("unit", ""),
                    "mom": s.get("mo_m"),
                    "yoy": s.get("yo_y"),
                })

            # 从 describe_slow_log_time_series_stats 获取准确的慢查询总数
            try:
                ts_result = client.dbw.describe_slow_log_time_series_stats({
                    "instance_id": p["instance_id"],
                    "DSType": p["instance_type"],
                    "start_time": end_time - 3600,
                    "end_time": end_time,
                    "interval": 3600,
                })
                if isinstance(ts_result, dict):
                    total_slow = sum(
                        pt.get("count", 0)
                        for pt in ts_result.get("slow_log_count_stats", [])
                    )
                    metrics.append({"name": "慢查询数量", "total": total_slow})
            except Exception:
                pass

            return _ok({
                "instance_id": p["instance_id"],
                "node_ids": _node_ids,
                "metrics": metrics,
            }, f"共 {len(metrics)} 项健康指标", context=ctx)

        return _to_result(result, "查询健康概览成功", context=ctx)
    except Exception as e:
        return _wrap_exception("describe_health_summary", e)


# ──────────────────────────────────────────────
# 公开函数：监控指标
# ──────────────────────────────────────────────

def get_metric_data(
    client: ToolboxClient,
    metric_name: str,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    period: int = 60,
    node_id: Optional[str] = None,
) -> dict[str, Any]:
    """获取监控指标数据。"""
    try:
        if not metric_name or not start_time or not end_time:
            return _error("metric_name, start_time, end_time 不能为空")
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("get_metric_data", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        req = {
            "InstanceType": p["instance_type"],
            "MetricName": metric_name,
            "Period": period,
            "StartTime": start_time,
            "EndTime": end_time,
            "Filters": [{"InstanceId": p["instance_id"]}],
        }
        if node_id:
            req["Filters"][0]["NodeId"] = node_id

        result = client.dbw.get_metric_data(req)
        return _to_result(result, "获取监控数据成功", context=ctx)
    except Exception as e:
        return _wrap_exception("get_metric_data", e)


def get_metric_items(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
) -> dict[str, Any]:
    """获取可用的监控指标项。"""
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("get_metric_items", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        result = client.dbw.get_metric_items({"InstanceType": p["instance_type"]})
        return _to_result(result, "获取监控指标项成功", context=ctx)
    except Exception as e:
        return _wrap_exception("get_metric_items", e)


def describe_table_metric(
    client: ToolboxClient,
    db_name: str,
    table: str,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    table_sql_type: str = "DML",
) -> dict[str, Any]:
    """获取表级别监控指标（按 SQL 类型统计执行次数/耗时趋势）。

    table_sql_type: 仅支持 "DML" 或 "DDL"，默认 "DML"。
    """
    try:
        if table_sql_type not in ("DML", "DDL"):
            return _error("table_sql_type 仅支持 DML 或 DDL")
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_table_metric", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        req = {
            "InstanceId": p["instance_id"],
            "InstanceType": p["instance_type"],
            "TableSqlType": table_sql_type,
            "DbName": db_name,
            "Table": table,
            "StartTime": start_time,
            "EndTime": end_time,
        }
        result = client.dbw.describe_table_metric(req)
        return _to_result(result, "获取表监控成功", context=ctx)
    except Exception as e:
        return _wrap_exception("describe_table_metric", e)



# ──────────────────────────────────────────────
# 公开函数：会话与进程
# ──────────────────────────────────────────────

def list_connections(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    show_sleep: bool = False,
    page_number: int = 1,
    page_size: int = 50,
    node_id: Optional[str] = None,
    users: Optional[Union[str, List[str]]] = None,
    hosts: Optional[Union[str, List[str]]] = None,
    dbs: Optional[Union[str, List[str]]] = None,
    command_type: Optional[str] = None,
    min_time: Optional[int] = None,
    sql: Optional[str] = None,
    fuzzy_match: bool = True,
) -> dict[str, Any]:
    """查询实时连接列表。show_sleep=True 时包含 Sleep 连接。
    VeDB 实例自动查询所有节点并合并结果。
    筛选参数通过 API 服务端过滤：users/hosts/dbs 支持字符串或列表（≤10），
    min_time 筛选执行时间≥N秒，sql 匹配 SQL 语句，
    fuzzy_match 控制模糊匹配（默认 True）。
    """
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        blocked = _check_supported("list_connections", p["instance_type"], ctx)
        if blocked:
            return blocked

        # 构建 QueryFilter（服务端过滤）
        def _to_csv(val: Union[str, List[str]]) -> str:
            return ",".join(val) if isinstance(val, list) else val

        qf_base: dict[str, Any] = {"ShowSleepConnection": show_sleep}
        if users:
            qf_base["User"] = _to_csv(users)
        if hosts:
            qf_base["Host"] = _to_csv(hosts)
        if dbs:
            qf_base["DB"] = _to_csv(dbs)
        if command_type:
            qf_base["Command"] = command_type
        if min_time is not None:
            qf_base["LowerExecTimeLimit"] = str(min_time)
        if sql:
            qf_base["Info"] = sql
        if any([users, hosts, dbs, command_type, min_time is not None, sql]):
            qf_base["isFuzzy"] = fuzzy_match

        # 确定要查询的节点
        node_ids_to_query: list[str] = []
        node_id_map: dict[str, str] = {}  # node_id → node_type
        if p["instance_type"] == "VeDBMySQL":
            if node_id:
                # VeDB 指定节点：只查该节点
                node_ids_to_query = [node_id]
            else:
                # VeDB 未指定：自动查所有节点
                try:
                    nodes = client.dbw.describe_instance_nodes({
                        "DSType": p["instance_type"],
                        "InstanceId": p["instance_id"],
                    })
                    for n in nodes.get("nodes_info", []):
                        nid = n.get("node_id", "")
                        if nid:
                            node_ids_to_query.append(nid)
                            node_id_map[nid] = n.get("node_type", "")
                except Exception:
                    pass
        else:
            # 非 VeDB：node_id 作为 QueryFilter 传给服务端
            if node_id:
                qf_base["NodeId"] = node_id

        def _parse_sessions(raw: list[dict], nid: str = "", ntype: str = "") -> list[dict]:
            sessions = []
            for d in raw:
                s = {
                    "process_id": d.get("ProcessID") or d.get("process_id", ""),
                    "user": d.get("User") or d.get("user", ""),
                    "host": d.get("Host") or d.get("host", ""),
                    "db": d.get("DB") or d.get("db", ""),
                    "command": d.get("Command") or d.get("command", ""),
                    "time": d.get("Time") or d.get("time", 0),
                    "state": d.get("State") or d.get("state", ""),
                    "info": d.get("Info") or d.get("info", ""),
                }
                if nid:
                    s["node_id"] = nid
                    s["node_type"] = ntype
                sessions.append(s)
            return sessions

        def _fetch_node(nid: str) -> list[dict]:
            """拉取单个节点的会话。"""
            qf = {**qf_base, "NodeId": nid}
            req = {
                "InstanceId": p["instance_id"],
                "DSType": p["instance_type"],
                "PageNumber": 1,
                "PageSize": 200,
                "QueryFilter": qf,
            }
            res = client.dbw.describe_dialog_infos(req)
            if not isinstance(res, dict):
                return []
            details = res.get("details") or res.get("Details") or {}
            dlist = details.get("dialog_details") or details.get("DialogDetails") or []
            return _parse_sessions(dlist, nid, node_id_map.get(nid, ""))

        all_sessions: list[dict] = []

        if node_ids_to_query:
            # VeDB: 并发拉全量，合并后统一分页
            with ThreadPoolExecutor(max_workers=len(node_ids_to_query)) as pool:
                futures = [pool.submit(_fetch_node, nid) for nid in node_ids_to_query]
                for fut in as_completed(futures):
                    all_sessions.extend(fut.result())
            all_sessions.sort(key=lambda s: float(s.get("time", 0)), reverse=True)
            total = len(all_sessions)
            start = (page_number - 1) * page_size
            paged = all_sessions[start:start + page_size]
            result_data: dict[str, Any] = {
                "total": total, "page_number": page_number, "page_size": page_size,
                "returned_count": len(paged), "sessions": paged,
            }
            # 大数据量时自动计算统计摘要 + 落盘全量数据
            if total > 100:
                result_data["stats"] = _compute_connection_stats(all_sessions)
                artifact = _dump_artifact(
                    {"sessions": all_sessions},
                    label="connections", description=f"全量连接数据({total}条)")
                if artifact:
                    result_data["artifact_path"] = artifact
            return _ok(result_data,
                       f"共 {total} 个实时会话，本页返回 {len(paged)} 个", context=ctx)
        else:
            # 非 VeDB：直接透传分页参数
            req = {
                "InstanceId": p["instance_id"],
                "DSType": p["instance_type"],
                "PageNumber": page_number,
                "PageSize": page_size,
                "QueryFilter": qf_base,
            }
            res = client.dbw.describe_dialog_infos(req)
            if not isinstance(res, dict):
                return _to_result(res, "查询实时会话成功", context=ctx)
            details = res.get("details") or res.get("Details") or {}
            dlist = details.get("dialog_details") or details.get("DialogDetails") or []
            total = details.get("total", details.get("Total", len(dlist)))
            sessions = _parse_sessions(dlist)
            sessions.sort(key=lambda s: float(s.get("time", 0)), reverse=True)
            result_data: dict[str, Any] = {
                "total": total, "page_number": page_number, "page_size": page_size,
                "returned_count": len(sessions), "sessions": sessions,
            }
            # 当前页数据较多时计算统计摘要（帮助 Agent 快速了解分布）
            if len(sessions) >= 50:
                result_data["stats"] = _compute_connection_stats(sessions)
                if total > len(sessions):
                    result_data["stats"]["note"] = (
                        f"统计基于当前页 {len(sessions)} 条数据，"
                        f"总共 {total} 条。如需全量统计请翻页拉取。")
            return _ok(result_data,
                       f"共 {total} 个实时会话，本页返回 {len(sessions)} 个", context=ctx)
    except Exception as e:
        return _wrap_exception("list_connections", e)



def list_history_connections(
    client: ToolboxClient,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    snapshot_time: Optional[int] = None,
    show_sleep: bool = False,
    sort_by: str = "time",
    page_number: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """查询历史连接快照。需实例已开启会话快照采集。

    start_time/end_time: Unix 时间戳，定义快照搜索范围。
    snapshot_time: 指定查询某个快照时间点，未传时取范围内最新快照。
    sort_by: 排序字段（time/user/db/command）。
    返回该时间点的连接列表及按 user/db/command 的聚合统计。
    """
    try:
        if not start_time or not end_time:
            return _error("start_time 和 end_time 不能为空")
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        blocked = _check_supported("list_history_connections", p["instance_type"], ctx)
        if blocked:
            return blocked

        # 1. 检查快照是否开启
        status = client.dbw.describe_snapshot_collection_status({
            "InstanceId": p["instance_id"],
            "InstanceType": p["instance_type"],
            "RegionId": p["region"],
        })
        snap_types = status.get("das_snap_shot_lists") or status.get("DasSnapShotLists") or []
        if "Dialog" not in snap_types:
            return _error(
                "该实例未开启会话快照采集。请在火山引擎控制台 → 数据库工作台 → "
                "可观测性 → 会话 → 开启会话快照后重试。",
                context=ctx,
            )

        # 2. 获取节点列表（VeDB 多节点）
        node_ids: list[str] = []
        node_type_map: dict[str, str] = {}
        is_vedb = p["instance_type"] == "VeDBMySQL"
        if is_vedb:
            try:
                nodes = client.dbw.describe_instance_nodes({
                    "DSType": p["instance_type"],
                    "InstanceId": p["instance_id"],
                })
                for n in nodes.get("nodes_info", []):
                    nid = n.get("node_id", "")
                    if nid:
                        node_ids.append(nid)
                        node_type_map[nid] = n.get("node_type", "")
            except Exception:
                pass

        # 3. 获取快照时间线（从第一个节点或不传 NodeId）
        snap_req: dict[str, Any] = {
            "Component": "DBEngine",
            "InstanceId": p["instance_id"],
            "DSType": p["instance_type"],
            "StartTime": start_time,
            "EndTime": end_time,
            "PageNumber": 1,
            "PageSize": 200,
        }
        if node_ids:
            snap_req["NodeId"] = node_ids[0]
        snap_result = client.dbw.describe_dialog_snapshots(snap_req)
        snapshots = snap_result.get("dialog_snapshots") or snap_result.get("DialogSnapshots") or []
        if not snapshots:
            return _ok({"total": 0, "connections": [], "snapshots_available": 0,
                         "summary": {}},
                       "该时间范围内无快照数据", context=ctx)

        # 4. 确定查询的快照时间点
        snap_times = sorted([s.get("snapshot_time", 0) for s in snapshots], reverse=True)
        target_time = snapshot_time
        if not target_time:
            target_time = snap_times[0]  # 最新快照
        elif target_time not in snap_times:
            # 找最近的快照
            target_time = min(snap_times, key=lambda t: abs(t - snapshot_time))

        # 5. 获取快照详情
        def _fetch_snapshot(nid: str | None) -> list[dict]:
            req: dict[str, Any] = {
                "InstanceId": p["instance_id"],
                "DSType": p["instance_type"],
                "SnapshotTime": target_time,
                "PageNumber": 1,
                "PageSize": 200,
                "Component": "DBEngine",
                "QueryFilter": {"ShowSleepConnection": show_sleep},
            }
            if nid:
                req["NodeId"] = nid
            res = client.dbw.describe_dialog_detail_snapshot(req)
            return res.get("dialog_details") or res.get("DialogDetails") or []

        raw_connections: list[dict] = []
        if node_ids:
            # VeDB: 并发查所有节点
            with ThreadPoolExecutor(max_workers=len(node_ids)) as pool:
                futures = [pool.submit(_fetch_snapshot, nid) for nid in node_ids]
                for fut in as_completed(futures):
                    raw_connections.extend(fut.result())
        else:
            raw_connections = _fetch_snapshot(None)

        # 6. 解析连接
        connections = []
        for d in raw_connections:
            time_val = d.get("time") or d.get("Time", "0")
            if isinstance(time_val, str):
                time_val = int(time_val.rstrip("s")) if time_val.rstrip("s").isdigit() else 0
            connections.append({
                "process_id": d.get("process_id") or d.get("ProcessID", ""),
                "user": d.get("user") or d.get("User", ""),
                "host": d.get("host") or d.get("Host", ""),
                "db": d.get("db") or d.get("DB", ""),
                "command": d.get("command") or d.get("Command", ""),
                "time": time_val,
                "state": d.get("state") or d.get("State", ""),
                "info": d.get("info") or d.get("Info", ""),
                "node_id": d.get("node_id") or d.get("NodeId", ""),
                "blocking_pid": d.get("blocking_pid") or d.get("BlockingPid", ""),
            })

        # 7. 聚合统计
        from collections import Counter
        by_user = Counter(c["user"] for c in connections)
        by_db = Counter(c["db"] for c in connections)
        by_command = Counter(c["command"] for c in connections)
        summary = {
            "by_user": dict(by_user.most_common(10)),
            "by_db": dict(by_db.most_common(10)),
            "by_command": dict(by_command.most_common(10)),
        }

        # 8. 排序
        sort_key = sort_by if sort_by in ("user", "db", "command", "time") else "time"
        reverse = sort_key == "time"
        connections.sort(key=lambda c: c.get(sort_key, ""), reverse=reverse)

        # 9. 分页
        total = len(connections)
        start_idx = (page_number - 1) * page_size
        paged = connections[start_idx:start_idx + page_size]

        return _ok({
            "total": total,
            "connections": paged,
            "snapshot_time": target_time,
            "snapshots_available": len(snap_times),
            "summary": summary,
        }, f"快照时间 {target_time}，共 {total} 个连接", context=ctx)
    except Exception as e:
        return _wrap_exception("list_history_connections", e)


def kill_process(
    client: ToolboxClient,
    process_ids: Optional[List[str]] = None,
    node_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    shard_id: Optional[str] = None,
    kill_all: bool = False,
    users: Optional[Union[str, List[str]]] = None,
    hosts: Optional[Union[str, List[str]]] = None,
    dbs: Optional[Union[str, List[str]]] = None,
    command_type: Optional[str] = None,
    min_time: Optional[int] = None,
    sql: Optional[str] = None,
) -> dict[str, Any]:
    """终止进程。

    模式 1（精确终止）：传 process_ids + node_id，直接终止指定进程。
    模式 2（按条件终止）：传 kill_all=True 或筛选条件，
    通过 list_connections 服务端筛选获取匹配会话后批量终止。
    """
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        # 模式 1：精确终止
        if process_ids and node_id:
            pi: dict[str, Any] = {"ProcessIDs": process_ids, "NodeId": node_id}
            if shard_id:
                pi["ShardId"] = shard_id
            req = {
                "InstanceId": p["instance_id"],
                "DSType": p["instance_type"],
                "ProcessInfo": [pi],
            }
            result = client.dbw.kill_process(req)
            return _to_result(result, f"已终止 {len(process_ids)} 个进程", context=ctx)

        # 模式 2：按条件终止
        has_filter = kill_all or users or hosts or dbs or command_type or min_time is not None or sql
        if not has_filter:
            return _error(
                "需提供 process_ids+node_id（精确终止）或筛选条件（kill_all/users/hosts/dbs/command_type/min_time/sql）",
                context=ctx,
            )

        # 通过 list_connections 服务端筛选获取匹配会话
        conn_result = list_connections(
            client, instance_id=p["instance_id"],
            show_sleep=True, page_size=200,
            users=users, hosts=hosts, dbs=dbs, command_type=command_type,
            min_time=min_time, sql=sql, fuzzy_match=False,
        )
        if not conn_result.get("success"):
            return _error(f"获取会话列表失败: {conn_result.get('message', '')}", context=ctx)

        sessions = conn_result.get("data", {}).get("sessions", [])
        if not sessions:
            return _ok({"killed": 0}, "没有匹配的会话", context=ctx)

        # 按 node_id 分组
        node_groups: dict[str, list[str]] = {}
        no_node_pids: list[str] = []
        for s in sessions:
            pid = str(s.get("process_id", ""))
            if not pid:
                continue
            nid = s.get("node_id", "")
            if nid:
                node_groups.setdefault(nid, []).append(pid)
            else:
                no_node_pids.append(pid)

        # 非 VeDB 会话没有 node_id，需获取 Primary 节点
        if no_node_pids:
            primary_nid = node_id or ""
            if not primary_nid:
                try:
                    nodes = client.dbw.describe_instance_nodes({
                        "DSType": p["instance_type"],
                        "InstanceId": p["instance_id"],
                    })
                    for n in nodes.get("nodes_info", []):
                        if n.get("node_type") == "Primary":
                            primary_nid = n.get("node_id", "")
                            break
                    if not primary_nid:
                        all_nodes = nodes.get("nodes_info", [])
                        if all_nodes:
                            primary_nid = all_nodes[0].get("node_id", "")
                except Exception:
                    pass
            if not primary_nid:
                return _error("无法获取节点 ID，请手动指定 node_id", context=ctx)
            node_groups.setdefault(primary_nid, []).extend(no_node_pids)

        # 构建 ProcessInfo 并执行
        process_info_list = []
        for nid, pids in node_groups.items():
            info: dict[str, Any] = {"ProcessIDs": pids, "NodeId": nid}
            if shard_id:
                info["ShardId"] = shard_id
            process_info_list.append(info)

        req = {
            "InstanceId": p["instance_id"],
            "DSType": p["instance_type"],
            "ProcessInfo": process_info_list,
        }
        total_killed = sum(len(pids) for pids in node_groups.values())
        result = client.dbw.kill_process(req)
        return _to_result(result, f"已终止 {total_killed} 个匹配会话", context=ctx)

    except Exception as e:
        return _wrap_exception("kill_process", e)


# ──────────────────────────────────────────────
# 公开函数：锁与事务
# ──────────────────────────────────────────────

def _analyze_trx_and_lock(
    client: ToolboxClient,
    diagnosis_type: str,
    func_name: str,
    instance_id: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 50,
    search_param: Optional[dict] = None,
) -> dict[str, Any]:
    """内部公共函数：触发事务/锁分析并获取结果（仅 Primary 节点）。

    流程：查询 Primary 节点 → 触发 AnalyzeTrxAndLock → 用返回的
    DiagnosisTime 调 DescribeTrxAndLockAnalysisTaskResults 获取结果。
    """
    prep = _prepare(client, instance_id=instance_id)
    if not prep["ok"]:
        return prep["error"]
    p, ctx = prep["params"], prep["ctx"]

    unsupported = _check_supported(func_name, p["instance_type"], ctx)
    if unsupported:
        return unsupported

    # 1. 获取 Primary 节点（事务与锁分析仅支持 Primary）
    node_ids: list[str] = []
    try:
        nodes = client.dbw.describe_instance_nodes({
            "DSType": p["instance_type"],
            "InstanceId": p["instance_id"],
        })
        for n in nodes.get("nodes_info", []):
            if n.get("node_type") == "Primary":
                nid = n.get("node_id", "")
                if nid:
                    node_ids.append(nid)
                break
        if not node_ids:
            # 无 Primary 标记则取第一个节点
            all_nodes = nodes.get("nodes_info", [])
            if all_nodes and all_nodes[0].get("node_id"):
                node_ids.append(all_nodes[0]["node_id"])
    except Exception:
        pass

    if not node_ids:
        return _error("未找到实例节点，无法执行分析", context=ctx)

    # 2. 对 Primary 节点触发分析 + 获取结果
    nid = node_ids[0]
    trigger_req = {
        "InstanceId": p["instance_id"],
        "DSType": p["instance_type"],
        "DiagnosisType": diagnosis_type,
        "NodeId": nid,
        "RegionId": p["region"],
        "Trigger": "Manual",
    }
    trigger_res = client.dbw.analyze_trx_and_lock(trigger_req)
    diagnosis_time = trigger_res.get("diagnosis_time") or trigger_res.get("DiagnosisTime")
    if not diagnosis_time:
        return _error(f"节点 {nid} 未返回 DiagnosisTime", context=ctx)

    result_req = {
        "InstanceId": p["instance_id"],
        "DSType": p["instance_type"],
        "DiagnosisType": diagnosis_type,
        "DiagnosisTime": diagnosis_time,
        "NodeId": nid,
        "RegionId": p["region"],
        "PageNumber": page_number,
        "PageSize": min(page_size, 100),
    }
    _FILTER_KEY = {
        "TrxAndLock": "TrxAndLockQueryFilter",
        "Deadlock": "TrxAndLockQueryFilter",
        "LockWait": "LockWaitQueryFilter",
    }
    filter_key = _FILTER_KEY.get(diagnosis_type)
    if filter_key:
        result_req[filter_key] = search_param or {}
    analysis_data = client.dbw.describe_trx_and_lock_analysis_task_results(result_req)

    # 3. 按 diagnosis_type 提取对应列表
    _LIST_KEY = {
        "TrxAndLock": "trx_and_lock_list",
        "Deadlock": "deadlock_list",
        "LockWait": "lock_wait_list",
    }
    items = analysis_data.get(_LIST_KEY.get(diagnosis_type, "")) or []
    if not isinstance(items, list):
        items = []
    for item in items:
        if isinstance(item, dict):
            item["node_id"] = nid
            # 裁剪 lock_list：去除冗余的 lock_id/trx_id，保留摘要统计 + 最多 5 条代表性锁
            lock_list = item.get("lock_list")
            if isinstance(lock_list, list):
                for lk in lock_list:
                    lk.pop("lock_id", None)
                    lk.pop("trx_id", None)
                if len(lock_list) > 5:
                    summary: dict[str, int] = {}
                    for lk in lock_list:
                        key = f"{lk.get('lock_type','')}/{lk.get('lock_model','')}/{lk.get('lock_property','')}"
                        summary[key] = summary.get(key, 0) + 1
                    item["lock_summary"] = summary
                    item["lock_count"] = len(lock_list)
                    item["lock_list"] = lock_list[:5]

    total = analysis_data.get("total") or analysis_data.get("Total") or len(items)
    returned_count = len(items)

    result_data = {
        "total": total,
        "page_number": page_number,
        "page_size": page_size,
        "returned_count": returned_count,
        "diagnosis_time": diagnosis_time,
        "node_id": nid,
        "items": items,
    }

    type_label = {"TrxAndLock": "事务和锁", "Deadlock": "死锁", "LockWait": "锁等待"}
    label = type_label.get(diagnosis_type, diagnosis_type)
    return _ok(result_data, f"{label}分析完成，返回 {returned_count}/{total} 条记录（第 {page_number} 页）", context=ctx)


def describe_instance_nodes(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
) -> dict[str, Any]:
    """查询实例节点列表。用于获取 node_id（VeDB describe_deadlock 等场景需要）。"""
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_instance_nodes", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        result = client.dbw.describe_instance_nodes({
            "DSType": p["instance_type"],
            "InstanceId": p["instance_id"],
        })

        nodes = result.get("nodes_info") or []
        return _ok({"total": len(nodes), "nodes": nodes}, f"共 {len(nodes)} 个节点", context=ctx)
    except Exception as e:
        return _wrap_exception("describe_instance_nodes", e)


def describe_deadlock(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """触发死锁分析并返回结果。自动查询 Primary 节点执行分析。"""
    try:
        return _analyze_trx_and_lock(
            client, "Deadlock", "describe_deadlock",
            instance_id=instance_id,
            page_number=page_number, page_size=page_size, search_param=None,
        )
    except Exception as e:
        return _wrap_exception("describe_deadlock", e)


def describe_trx_and_locks(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 50,
    lock_status: Optional[str] = None,
    trx_status: Optional[str] = None,
    process_id: Optional[str] = None,
    trx_id: Optional[str] = None,
    block_trx_id: Optional[str] = None,
) -> dict[str, Any]:
    """触发事务和锁分析并返回结果。自动查询 Primary 节点执行分析。
    lock_status: "LockHold"（仅持锁）/ "LockWait"（仅等锁）/ "LockHoldAndWait"
    trx_status: "RUNNING" / "LOCKWAIT" / "ROLLING_BACK" / "COMMITTING"
    process_id / trx_id / block_trx_id: 精确匹配。"""
    try:
        search_param: dict[str, Any] = {}
        if lock_status:
            search_param["LockStatus"] = lock_status
        if trx_status:
            search_param["TrxStatus"] = trx_status
        if process_id:
            search_param["ProcessId"] = process_id
        if trx_id:
            search_param["TrxId"] = trx_id
        if block_trx_id:
            search_param["BlockTrxId"] = block_trx_id

        return _analyze_trx_and_lock(
            client, "TrxAndLock", "describe_trx_and_locks",
            instance_id=instance_id,
            page_number=page_number, page_size=page_size,
            search_param=search_param if search_param else None,
        )
    except Exception as e:
        return _wrap_exception("describe_trx_and_locks", e)


def describe_lock_wait(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 50,
    r_trx_state: Optional[str] = None,
    b_trx_state: Optional[str] = None,
    r_trx_id: Optional[str] = None,
    b_trx_id: Optional[str] = None,
) -> dict[str, Any]:
    """触发锁等待分析并返回结果。自动查询 Primary 节点执行分析。
    r_trx_state: 等待方（被阻塞）事务状态 "RUNNING" / "LOCKWAIT" / "ROLLING_BACK" / "COMMITTING"
    b_trx_state: 阻塞方事务状态（同上）
    r_trx_id / b_trx_id: 精确匹配事务 ID。"""
    try:
        search_param: dict[str, Any] = {}
        if r_trx_state:
            search_param["RTrxState"] = r_trx_state
        if b_trx_state:
            search_param["BTrxState"] = b_trx_state
        if r_trx_id:
            search_param["RTrxId"] = r_trx_id
        if b_trx_id:
            search_param["BTrxId"] = b_trx_id

        return _analyze_trx_and_lock(
            client, "LockWait", "describe_lock_wait",
            instance_id=instance_id,
            page_number=page_number, page_size=page_size,
            search_param=search_param if search_param else None,
        )
    except Exception as e:
        return _wrap_exception("describe_lock_wait", e)


def create_trx_export_task(
    client: ToolboxClient,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
) -> dict[str, Any]:
    """创建事务导出任务。"""
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("create_trx_export_task", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        req = {
            "InstanceId": p["instance_id"],
            "InstanceType": p["instance_type"],
            "StartTime": start_time,
            "EndTime": end_time,
        }
        result = client.dbw.create_trx_export_task(req)
        return _to_result(result, "创建事务导出任务成功", context=ctx)
    except Exception as e:
        return _wrap_exception("create_trx_export_task", e)



# ──────────────────────────────────────────────
# 公开函数：日志与空间
# ──────────────────────────────────────────────

def describe_err_logs(
    client: ToolboxClient,
    start_time: int,
    end_time: int,
    instance_id: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
) -> dict[str, Any]:
    """查询错误日志。"""
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_err_logs", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        req = {
            "InstanceId": p["instance_id"],
            "InstanceType": p["instance_type"],
            "StartTime": start_time,
            "EndTime": end_time,
            "PageNumber": page_number,
            "PageSize": page_size,
        }
        if keyword:
            req["SearchParam"] = {"Keyword": keyword}

        result = client.dbw.describe_err_logs(req)
        return _to_result(result, "查询错误日志成功", context=ctx)
    except Exception as e:
        return _wrap_exception("describe_err_logs", e)


def describe_table_space(
    client: ToolboxClient,
    instance_id: Optional[str] = None,
    database: Optional[str] = None,
    table_name: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """查询表空间详情。"""
    try:
        prep = _prepare(client, instance_id=instance_id)
        if not prep["ok"]:
            return prep["error"]
        p, ctx = prep["params"], prep["ctx"]

        unsupported = _check_supported("describe_table_space", p["instance_type"], ctx)
        if unsupported:
            return unsupported

        req = {
            "InstanceId": p["instance_id"],
            "InstanceType": p["instance_type"],
            "PageNumber": page_number,
            "PageSize": page_size,
        }
        if database:
            req["Database"] = database
        if table_name:
            req["TableName"] = table_name

        result = client.dbw.describe_table_space(req)
        return _to_result(result, "查询表空间详情成功", context=ctx)
    except Exception as e:
        return _wrap_exception("describe_table_space", e)


def describe_table_spaces(
    client: ToolboxClient,
    session_id: str,
    page_number: int = 1,
    page_size: int = 10,
    query: Optional[str] = None,
) -> dict[str, Any]:
    """查询表空间列表。"""
    try:
        if not session_id:
            return _error("session_id 不能为空")

        req = {
            "SessionId": session_id,
            "PageNumber": page_number,
            "PageSize": page_size,
        }
        if query:
            req["Query"] = query

        result = client.dbw.describe_table_spaces(req)
        return _to_result(result, "查询表空间列表成功")
    except Exception as e:
        return _wrap_exception("describe_table_spaces", e)


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Database Toolbox CLI")
    parser.add_argument("action", help="方法名")
    parser.add_argument("--data", default="{}", help="JSON参数")
    args = parser.parse_args()

    # 环境管理函数不需要 client
    if args.action == "check_env":
        print(json.dumps(check_env(), ensure_ascii=False, indent=2))
        return
    if args.action == "update_env":
        payload = json.loads(args.data)
        print(json.dumps(update_env(**payload), ensure_ascii=False, indent=2))
        return

    client = create_client()
    fn = globals().get(args.action)
    if fn is None or not callable(fn):
        print(json.dumps({"success": False, "message": f"不支持的方法: {args.action}"}))
        return

    try:
        payload = json.loads(args.data)
        result = fn(client, **payload)
        if hasattr(result, "to_json"):
            print(result.to_json(orient="records", force_ascii=False))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"success": False, "message": str(e)}))


if __name__ == "__main__":
    main()
