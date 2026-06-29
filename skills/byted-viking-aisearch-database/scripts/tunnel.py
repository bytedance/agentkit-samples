"""
Database Tunnel - 精简版数据库工具封装

此模块提供 DatabaseTunnel 类，用于与火山引擎 Database Toolbox API 交互。
只包含核心的数据库查询能力：列出数据库、表、表结构、执行SQL、nl2sql。

返回值统一格式:
    {
        "success": true/false,
        "message": "描述信息",
        "data": {...}
    }
"""

import os
import base64
import time
import json
import tempfile
from typing import Any, Optional, List

from scripts.dbw_client import DBWClient


_CONFIG_KEYS = {
    "region": "VOLCENGINE_REGION",
    "instance_id": "VOLCENGINE_INSTANCE_ID",
    "instance_type": "VOLCENGINE_INSTANCE_TYPE",
    "database": "VOLCENGINE_DATABASE",
    "api_url": "DATABASE_VIKING_APIG_URL",
    "dbw_credential": "DATABASE_VIKING_APIG_KEY",
    "tip_credential": "VE_TIP_TOKEN",
}


def _load_dotenv_file(dotenv_path: str = "~/.openclaw/.env") -> dict[str, str]:
    """Load ~/.openclaw/.env as a fallback config source."""
    dotenv_map: dict[str, str] = {}
    resolved_path = os.path.expanduser(dotenv_path)
    if not os.path.isfile(resolved_path):
        return dotenv_map

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                if key and value:
                    dotenv_map[key] = value
    except Exception:
        return {}

    return dotenv_map


def _load_config_value(
    key: str, dotenv_map: Optional[dict[str, str]] = None
) -> Optional[str]:
    """Prefer ~/.openclaw/.env, then fall back to the process environment."""
    if dotenv_map is None:
        dotenv_map = _load_dotenv_file()

    value = dotenv_map.get(key)
    if value is None or not str(value).strip():
        value = os.getenv(key)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


class SecurityCache:
    """安全管控状态缓存（文件缓存）"""

    def __init__(self, ttl_seconds: int = 30):
        self._ttl = ttl_seconds
        self._cache_dir = tempfile.gettempdir()
        self._cache_file = os.path.join(self._cache_dir, "dbw_security_cache.json")

    def _load_cache(self) -> dict:
        """从文件加载缓存"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_cache(self, cache: dict) -> None:
        """保存缓存到文件"""
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str) -> Optional[dict]:
        """获取缓存，如果过期返回 None"""
        cache = self._load_cache()
        if key in cache:
            entry = cache[key]
            if time.time() - entry["timestamp"] < self._ttl:
                return entry["data"]
            del cache[key]
            self._save_cache(cache)
        return None

    def set(self, key: str, data: dict) -> None:
        """设置缓存"""
        cache = self._load_cache()
        cache[key] = {"data": data, "timestamp": time.time()}
        self._save_cache(cache)

    def clear(self) -> None:
        """清空缓存"""
        self._save_cache({})


class DatabaseTunnel:
    """
    Database Tunnel 封装类

    提供对数据库的基础查询操作。
    初始化时可传入配置参数，也可从环境变量读取：
        VOLCENGINE_REGION, VOLCENGINE_INSTANCE_ID, VOLCENGINE_INSTANCE_TYPE, VOLCENGINE_DATABASE
        DATABASE_VIKING_APIG_URL, DATABASE_VIKING_APIG_KEY
    """

    def __init__(
        self,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        instance_type: Optional[str] = None,
        database: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        ve_tip_token: Optional[str] = None,
    ) -> None:
        dotenv_map = _load_dotenv_file()
        self.instance_info_list_raw = _load_config_value(
            "AISEARCH_DBW_INSTANCE_INFO_LIST", dotenv_map
        ) or _load_config_value("KNOWLEDGE_CENTER_DBW_INSTANCE_LIST", dotenv_map)
        self._explicit_config = (
            region,
            instance_id,
            instance_type,
            database,
            api_url,
            api_key,
            ve_tip_token,
        )
        self._client: Optional[DBWClient] = None
        self._dotenv_map = dotenv_map
        self._security_cache = SecurityCache(ttl_seconds=30)

    def _resolve_config_value(
        self,
        explicit_value: Optional[str],
        key: str,
        dotenv_map: Optional[dict[str, str]] = None,
    ) -> Optional[str]:
        if explicit_value not in (None, ""):
            return explicit_value
        return _load_config_value(key, dotenv_map)

    def _config_value(self, name: str) -> Optional[str]:
        names = (
            "region",
            "instance_id",
            "instance_type",
            "database",
            "api_url",
            "dbw_credential",
            "tip_credential",
        )
        return self._resolve_config_value(
            self._explicit_config[names.index(name)],
            _CONFIG_KEYS[name],
            self._dotenv_map,
        )

    @property
    def client(self) -> DBWClient:
        if self._client is None:
            self._client = DBWClient(
                self._config_value("region"),
                self._config_value("instance_id"),
                self._config_value("instance_type"),
                self._config_value("database"),
                self._config_value("api_url"),
                self._config_value("dbw_credential"),
                self._config_value("tip_credential"),
            )
        return self._client

    def _required(
        self,
        value: Optional[str],
        fallback: Optional[str],
        param_name: str,
        user_friendly_name: str,
    ) -> str:
        resolved = value if value not in (None, "") else fallback
        if not resolved:
            raise ValueError(
                f"缺少必要参数: {user_friendly_name} (参数名: {param_name})。请询问用户提供。"
            )
        return resolved

    def _normalize_instance_type(self, instance_id: str, instance_type: str) -> str:
        """Avoid sending External instances to DBW as hosted RDS instances."""
        if instance_id.startswith("External-") and instance_type != "External":
            return "External"
        return instance_type

    def _resolve_instance_params(
        self,
        instance_id: Optional[str],
        instance_type: Optional[str],
    ) -> tuple[str, str]:
        resolved_instance_id = self._required(
            instance_id,
            self._config_value("instance_id"),
            "instance_id",
            "数据库实例ID",
        )
        resolved_instance_type = self._required(
            instance_type,
            self._config_value("instance_type"),
            "instance_type",
            "实例类型",
        )
        return resolved_instance_id, self._normalize_instance_type(
            resolved_instance_id, resolved_instance_type
        )

    def _parse_instance_info_list_env(self) -> list[dict[str, Any]]:
        raw = self.instance_info_list_raw
        if not raw:
            return []
        raw = raw.strip()
        try:
            decoded = base64.b64decode(raw)
            decoded_text = decoded.decode("utf-8")
            data = json.loads(decoded_text)
        except Exception as e:
            raise ValueError(
                f"环境变量 AISEARCH_DBW_INSTANCE_INFO_LIST 不是合法的 base64(JSON): {e}"
            )

        if not isinstance(data, list):
            raise ValueError(
                "环境变量 AISEARCH_DBW_INSTANCE_INFO_LIST 需要是 JSON 数组。"
            )

        instances: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            instance_id = item.get("instance_id")
            instance_type = item.get("instance_type")
            region = item.get("region")
            if not instance_id or not instance_type:
                continue
            key = (str(instance_id), str(instance_type))
            if key in seen:
                continue
            seen.add(key)
            instance: dict[str, Any] = {
                "instance_id": str(instance_id),
                "instance_type": str(instance_type),
            }
            if region not in (None, ""):
                instance["region"] = str(region)
            instances.append(instance)
        return instances

    def list_instances(self) -> dict[str, Any]:
        try:
            instances = self._parse_instance_info_list_env()
            return self._ok(
                {"instances": instances, "total": len(instances)},
                f"共 {len(instances)} 个可访问实例",
            )
        except Exception as e:
            return self._error(str(e))

    def _ok(self, data: Any = None, message: str = "成功") -> dict[str, Any]:
        result = {"success": True, "message": message}
        if data is not None:
            result["data"] = data
        return result

    def _error(self, message: str, error_detail: Any = None) -> dict[str, Any]:
        result = {"success": False, "message": message}
        if error_detail:
            result["error"] = error_detail
        return result

    def _extract_db_engine(self, instance_id: str, instance_type: str) -> str:
        """从 instance_id 中提取 db_engine
        当 instance_type 为 External 时，instance_id 格式为: External-MySQL-xxx 或 External-Postgres-xxx
        """
        if instance_type == "External" and instance_id.startswith("External-"):
            parts = instance_id.split("-")
            if len(parts) >= 2:
                return parts[1]
        return "MySQL"

    def _handle_api_error(self, error_msg: str) -> dict[str, Any]:
        """处理 API 错误，返回用户友好的错误消息"""
        if "InvalidAccessKey" in error_msg or "InvalidSecretKey" in error_msg:
            return self._error(
                "AK/SK 认证失败，请检查 Access Key 和 Secret Key 是否正确。",
                {"type": "auth_error", "detail": error_msg},
            )
        if "signature" in error_msg.lower():
            return self._error(
                "签名验证失败，请检查 AK/SK 是否正确。",
                {"type": "auth_error", "detail": error_msg},
            )
        if "403" in error_msg:
            return self._error(
                "权限不足，请检查 AK/SK 是否有权限访问该资源。",
                {"type": "permission_denied", "detail": error_msg},
            )
        if "404" in error_msg:
            return self._error(
                "资源不存在，请检查 instance_id 是否正确。",
                {"type": "not_found", "detail": error_msg},
            )
        if "409" in error_msg or "CreateSessionError" in error_msg:
            return self._error(
                "无法连接到数据库实例，请检查实例是否正常运行，或者实例在该地域是否存在，或联系 DBA。",
                {"type": "connection_error", "detail": error_msg},
            )
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return self._error(
                "请求超时，请稍后重试。", {"type": "timeout", "detail": error_msg}
            )
        return self._error(
            f"API调用失败: {error_msg}", {"type": "api_error", "detail": error_msg}
        )

    def check_security_status(
        self,
        instance_id: str,
        instance_type: str,
    ) -> dict[str, Any]:
        """
        检查实例是否开启了安全管控

        Returns:
            开启安全管控:
                {"success": true, "data": {"enabled": true, "security_rule_id": "xxx"}}
            未开启安全管控:
                {"success": true, "data": {"enabled": false}}
            查询失败:
                {"success": false, "message": "错误信息"}
        """
        instance_type = self._normalize_instance_type(instance_id, instance_type)
        cache_key = f"{instance_id}:{instance_type}"
        cached = self._security_cache.get(cache_key)
        if cached is not None:
            return self._ok(cached, "从缓存获取")

        source = "Public" if instance_type.lower() == "external" else "Volc"

        try:
            req = {
                "InstanceID": instance_id,
                "InstanceType": instance_type,
                "Source": source,
            }
            result = self.client.describe_instance_management(req)
            # 处理两种返回格式：
            # 1. {"Result": {"SecurityRuleId": "xxx", ...}}
            # 2. {"security_rule_id": "xxx", ...} (直接返回)
            if isinstance(result, dict):
                # 优先检查 Result 字段
                result_data = result.get("Result")
                if result_data is None:
                    result_data = result

                if not isinstance(result_data, dict):
                    result_data = {}

                # 检查是否有安全管控相关字段
                security_rule_id = result_data.get(
                    "security_rule_id"
                ) or result_data.get("SecurityRuleId")
                if security_rule_id:
                    security_info = {
                        "enabled": True,
                        "security_rule_id": security_rule_id,
                        "security_rule": result_data.get("security_rule")
                        or result_data.get("SecurityRule", ""),
                        "approval_config": result_data.get("approval_config")
                        or result_data.get("ApprovalConfig", ""),
                    }
                    self._security_cache.set(cache_key, security_info)
                    return self._ok(security_info, "已开启安全管控")
            security_info = {"enabled": False}
            self._security_cache.set(cache_key, security_info)
            return self._ok(security_info, "未开启安全管控")

        except Exception as e:
            return self._handle_api_error(str(e))

    def _to_result(self, data: Any, message: str = "操作成功") -> dict[str, Any]:
        if data is None:
            return self._error("返回数据为空")
        if isinstance(data, dict):
            if "error" in data or "Error" in data:
                error_info = data.get("error") or data.get("Error")
                return self._error(f"API错误: {error_info}", data)
            return self._ok(data, message)
        return self._ok(data, message)

    def list_databases(
        self,
        instance_id: Optional[str] = None,
        instance_type: Optional[str] = None,
        page_number: Optional[int] = 1,
        page_size: Optional[int] = 10,
    ) -> dict[str, Any]:
        """
        列出数据库

        Returns:
            {
                "success": true,
                "data": {
                    "total": 10,
                    "page": 1,
                    "databases": [
                        {"name": "company", "charset": "utf8mb4", "collation": "utf8mb4_unicode_ci"}
                    ]
                }
            }
        """
        try:
            instance_id, instance_type = self._resolve_instance_params(
                instance_id, instance_type
            )

            security_check = self.check_security_status(instance_id, instance_type)
            if security_check.get("success"):
                security_data = security_check.get("data", {})
                if not security_data.get("enabled"):
                    return self._error(
                        "该实例未开启安全管控，无法执行操作。请到DBW控制台开启安全管控后再试。",
                        {"type": "security_not_enabled"},
                    )

            req = {
                "instance_id": instance_id,
                "instance_type": instance_type,
                "db_engine": self._extract_db_engine(instance_id, instance_type),
                "page_number": page_number or 1,
                "page_size": page_size or 10,
            }

            result = self.client.list_databases(req)

            if isinstance(result, dict):
                items = result.get("items") or []
                databases = []
                for item in items:
                    if not item:
                        continue
                    databases.append(
                        {
                            "name": item.get("name", ""),
                            "charset": item.get("character_set_name", ""),
                            "collation": item.get("collation_name", ""),
                            "is_system": item.get("is_system_db", False),
                            "description": item.get("description", ""),
                        }
                    )
                return self._ok(
                    {
                        "total": result.get("total", 0),
                        "page": page_number or 1,
                        "databases": databases,
                    },
                    f"共 {len(databases)} 个数据库",
                )

            return self._to_result(result)
        except Exception as e:
            return self._handle_api_error(str(e))

    def list_tables(
        self,
        instance_id: Optional[str] = None,
        instance_type: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        page_number: Optional[int] = 1,
        page_size: Optional[int] = 10,
    ) -> dict[str, Any]:
        """
        列出数据库中的表

        Args:
            schema: 数据库模式 (PostgreSQL 需要指定，如 public)

        Returns:
            {
                "success": true,
                "data": {
                    "total": 50,
                    "page": 1,
                    "database": "company",
                    "tables": ["users", "orders", "products"]
                }
            }
        """
        try:
            instance_id, instance_type = self._resolve_instance_params(
                instance_id, instance_type
            )
            database = self._required(
                database, self._config_value("database"), "database", "数据库名称"
            )

            security_check = self.check_security_status(instance_id, instance_type)
            if security_check.get("success"):
                security_data = security_check.get("data", {})
                if not security_data.get("enabled"):
                    return self._error(
                        "该实例未开启安全管控，无法执行操作。请到DBW控制台开启安全管控后再试。",
                        {"type": "security_not_enabled"},
                    )

            req = {
                "instance_id": instance_id,
                "instance_type": instance_type,
                "database": database,
                "page_number": page_number or 1,
                "page_size": page_size or 10,
            }

            if schema:
                req["schema"] = schema

            result = self.client.list_tables(req)

            if isinstance(result, dict):
                tables = result.get("items") or []
                return self._ok(
                    {
                        "total": result.get("total", len(tables)),
                        "page": page_number or 1,
                        "database": database,
                        "schema": schema,
                        "tables": tables,
                    },
                    f"共 {len(tables)} 张表",
                )

            if isinstance(result, list):
                return self._ok(
                    {
                        "total": len(result),
                        "page": page_number or 1,
                        "database": database,
                        "schema": schema,
                        "tables": result,
                    },
                    f"共 {len(result)} 张表",
                )

            return self._to_result(result)
        except Exception as e:
            return self._handle_api_error(str(e))

    def get_table_info(
        self,
        table: str,
        instance_id: Optional[str] = None,
        instance_type: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        获取表结构

        Args:
            schema: 数据库模式 (PostgreSQL 需要指定，如 public)

        Returns:
            {
                "success": true,
                "data": {
                    "name": "users",
                    "engine": "InnoDB",
                    "charset": "utf8mb4",
                    "columns": [
                        {
                            "name": "id",
                            "type": "bigint",
                            "nullable": false,
                            "primary_key": true,
                            "auto_increment": true,
                            "comment": "用户ID"
                        }
                    ]
                }
            }
        """
        try:
            instance_id, instance_type = self._resolve_instance_params(
                instance_id, instance_type
            )
            database = self._required(
                database, self._config_value("database"), "database", "数据库名称"
            )
            if not table:
                return self._error("table 参数不能为空，请询问用户提供表名。")

            security_check = self.check_security_status(instance_id, instance_type)
            if security_check.get("success"):
                security_data = security_check.get("data", {})
                if not security_data.get("enabled"):
                    return self._error(
                        "该实例未开启安全管控，无法执行操作。请到DBW控制台开启安全管控后再试。",
                        {"type": "security_not_enabled"},
                    )

            req = {
                "instance_id": instance_id,
                "instance_type": instance_type,
                "database": database,
                "table": table,
            }

            if schema:
                req["schema"] = schema

            result = self.client.get_table_info(req)
            if isinstance(result, dict):
                if result.get("status") == "error":
                    error_msg = result.get("message", "获取表结构失败")
                    if "doesn't exist" in error_msg or "不存在" in error_msg:
                        return self._error(
                            f"表 '{table}' 不存在，请检查表名是否正确。",
                            {"type": "table_not_found"},
                        )
                    return self._error(
                        f"获取表结构失败: {error_msg}", {"type": "api_error"}
                    )

                # 处理大小写字段名 (table_meta可能是大写或小写)
                table_meta = (
                    result.get("TableMeta") or result.get("table_meta") or result
                )
                if not isinstance(table_meta, dict):
                    table_meta = {}

                columns = table_meta.get("Columns") or table_meta.get("columns") or []
                normalized_columns = []
                if columns and isinstance(columns, list):
                    for col in columns:
                        normalized_columns.append(
                            {
                                "name": col.get("Name") or col.get("name", ""),
                                "type": col.get("Type") or col.get("type", ""),
                                "length": col.get("Length") or col.get("length", ""),
                                "nullable": col.get("AllowBeNull")
                                or col.get("allow_be_null", True),
                                "primary_key": col.get("IsPrimaryKey")
                                or col.get("is_primary_key", False),
                                "auto_increment": col.get("IsAutoIncrement")
                                or col.get("is_auto_increment", False),
                                "default": col.get("DefaultValue")
                                or col.get("default_value"),
                                "comment": col.get("Comment") or col.get("comment", ""),
                            }
                        )
                return self._ok(
                    {
                        "name": table_meta.get("Name") or table_meta.get("name", table),
                        "engine": table_meta.get("Engine")
                        or table_meta.get("engine", ""),
                        "charset": table_meta.get("CharacterSet")
                        or table_meta.get("character_set", ""),
                        "definition": table_meta.get("Definition")
                        or table_meta.get("definition", ""),
                        "columns": normalized_columns,
                    },
                    f"表 {table} 结构获取成功",
                )

            return self._to_result(result)
        except Exception as e:
            return self._handle_api_error(str(e))

    def _parse_rows(self, rows: Optional[list]) -> list:
        """解析行数据，支持多种格式"""
        if not rows:
            return []
        parsed_rows = []
        for row in rows:
            if isinstance(row, dict):
                if "cells" in row:
                    parsed_rows.append(row["cells"])
                elif "Cells" in row:
                    parsed_rows.append(row["Cells"])
                else:
                    parsed_rows.append(row)
            else:
                parsed_rows.append(row)
        return parsed_rows

    def _extract_error_info(
        self, result: dict, default_message: str = "SQL执行失败"
    ) -> tuple[str, dict]:
        """提取错误信息，返回 (用户友好的错误消息, 原始错误详情)"""
        reason_detail = result.get("reason_detail") or result.get("ReasonDetail") or ""

        if not isinstance(reason_detail, str):
            reason_detail = str(reason_detail)

        if "rule ID:" in reason_detail or "规则" in reason_detail:
            return (
                "SQL 被安全规则拦截，请通过工单系统执行该操作。",
                {"type": "security_blocked", "detail": reason_detail},
            )

        if "doesn't exist" in reason_detail or "不存在" in reason_detail:
            table_match = reason_detail.find("Table '")
            if table_match != -1:
                return (
                    "表不存在，请检查表名是否正确。",
                    {"type": "table_not_found", "detail": reason_detail},
                )

        return (default_message, {"type": "sql_error", "detail": reason_detail})

    def execute_sql(
        self,
        commands: str,
        instance_id: Optional[str] = None,
        instance_type: Optional[str] = None,
        database: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        执行 SQL 查询

        Args:
            commands: SQL 语句，一次只能执行一条

        Returns:
            成功时:
            {
                "success": true,
                "message": "查询成功",
                "data": {
                    "command_str": "SQL语句",
                    "state": "success|failed",
                    "row_count": 10,
                    "columns": ["id", "name"],
                    "rows": [{"id": 1, "name": "张三"}],
                    "execution_time_ms": 50
                }
            }
            失败时:
            {
                "success": false,
                "message": "SQL执行失败",
                "error": {
                    "state": "failed",
                    "reason_detail": "错误原因"
                }
            }
        """
        try:
            instance_id, instance_type = self._resolve_instance_params(
                instance_id, instance_type
            )
            database = self._required(
                database, self._config_value("database"), "database", "数据库名称"
            )
            if not commands:
                return self._error("commands 参数不能为空，请询问用户提供 SQL 语句。")

            security_check = self.check_security_status(instance_id, instance_type)
            if security_check.get("success"):
                security_data = security_check.get("data", {})
                if not security_data.get("enabled"):
                    return self._error(
                        "该实例未开启安全管控，无法执行 SQL。请到DBW控制台开启安全管控后再试。",
                        {"type": "security_not_enabled"},
                    )

            sql_with_comment = f"/*from: database-tunnel*/ {commands}"

            req = {
                "instance_id": instance_id,
                "instance_type": instance_type,
                "database": database,
                "commands": sql_with_comment,
                "time_out_seconds": 60,
            }

            result = self.client.execute_sql(req)

            if isinstance(result, dict):
                if (
                    "Results" in result
                    and isinstance(result["Results"], list)
                    and len(result["Results"]) > 0
                ):
                    first_result = result["Results"][0]
                    if not isinstance(first_result, dict):
                        return self._error("API 返回格式错误: first_result 不是字典")
                    state = first_result.get("State", "")
                    if state == "Success":
                        return self._ok(
                            {
                                "command_str": commands,
                                "state": state,
                                "row_count": first_result.get("RowCount", 0),
                                "columns": first_result.get("ColumnNames", []),
                                "rows": self._parse_rows(first_result.get("Rows", [])),
                                "run_time": first_result.get("RunTime", 0),
                                "running_info": first_result.get("RunningInfo", {}),
                            },
                            "查询成功",
                        )
                    else:
                        user_msg, error_detail = self._extract_error_info(
                            first_result, "SQL执行失败"
                        )
                        return self._error(user_msg, error_detail)

                if (
                    "results" in result
                    and isinstance(result["results"], list)
                    and len(result["results"]) > 0
                ):
                    first_result = result["results"][0]
                    if not isinstance(first_result, dict):
                        return self._error("API 返回格式错误: first_result 不是字典")
                    state = first_result.get("state", "")
                    if state == "Success":
                        return self._ok(
                            {
                                "command_str": commands,
                                "state": state,
                                "row_count": first_result.get("row_count", 0),
                                "columns": first_result.get("column_names", []),
                                "rows": self._parse_rows(first_result.get("rows", [])),
                                "run_time": first_result.get("run_time", 0),
                                "running_info": first_result.get("running_info", {}),
                            },
                            "查询成功",
                        )
                    else:
                        user_msg, error_detail = self._extract_error_info(
                            first_result, "SQL执行失败"
                        )
                        return self._error(user_msg, error_detail)

                state = result.get("state", "")
                if state == "success":
                    return self._ok(
                        {
                            "command_str": result.get("command_str", commands),
                            "state": state,
                            "row_count": result.get("row_count", 0),
                            "columns": result.get("column_names", []),
                            "rows": self._parse_rows(result.get("rows", [])),
                        },
                        "查询成功",
                    )
                else:
                    user_msg, error_detail = self._extract_error_info(
                        result, "SQL执行失败"
                    )
                    return self._error(user_msg, error_detail)
            return self._to_result(result, "执行完成")
        except Exception as e:
            return self._handle_api_error(str(e))

    def nl2sql(
        self,
        query: str,
        instance_id: Optional[str] = None,
        instance_type: Optional[str] = None,
        database: Optional[str] = None,
        tables: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        """
        自然语言转 SQL

        Args:
            query: 自然语言查询，例如 "查询最近一周的销售额"
            instance_id: 数据库实例ID
            instance_type: 实例类型 (MySQL/VeDBMySQL/Postgres)
            database: 数据库名称
            tables: 涉及的表名列表

        Returns:
            {
                "success": true,
                "message": "成功",
                "data": {
                    "query": "原始问题",
                    "sql": "生成的SQL",
                    "sql_type": "SELECT|INSERT|UPDATE|DELETE"
                }
            }
        """
        try:
            instance_id, instance_type = self._resolve_instance_params(
                instance_id, instance_type
            )
            database = self._required(
                database, self._config_value("database"), "database", "数据库名称"
            )
            if not query:
                return self._error("query 参数不能为空，请询问用户提供自然语言查询。")

            security_check = self.check_security_status(instance_id, instance_type)
            if security_check.get("success"):
                security_data = security_check.get("data", {})
                if not security_data.get("enabled"):
                    return self._error(
                        "该实例未开启安全管控，无法执行操作。请到DBW控制台开启安全管控后再试。",
                        {"type": "security_not_enabled"},
                    )

            req = {
                "instance_id": instance_id,
                "instance_type": instance_type,
                "database": database,
                "query": query,
            }
            if tables:
                req["tables"] = tables

            result = self.client.nl2sql(req)
            return self._to_result(result, "SQL生成成功")
        except Exception as e:
            return self._handle_api_error(str(e))
