from typing import Optional, List
import logging
from datetime import datetime, timezone
from .base import BaseTools
from ..utils import handle_errors, read_only_check

logger = logging.getLogger(__name__)


class DatabaseTools(BaseTools):
    """使用 REST API 方式执行 SQL"""
    async def _execute_sql_raw(self, query: str, workspace_id: Optional[str] = None) -> List[dict]:
        if not query or not query.strip():
            raise ValueError("SQL query cannot be empty")

        ws_id, branch_id = await self._resolve_target(workspace_id)
        logger.info(
            "Executing SQL query",
            extra={"workspace_id": ws_id, "branch_id": branch_id, "query_length": len(query)}
        )

        client = await self._get_client(ws_id, branch_id)
        result = await client.call_api("/pg/query", method="POST", json_data={"query": query})

        if isinstance(result, dict) and isinstance(result.get("data"), list):
            result = result["data"]
        if not isinstance(result, list):
            raise TypeError(f"Unexpected SQL result type: {type(result).__name__}")

        logger.debug(f"SQL query returned {len(result)} rows")
        return result

    @handle_errors
    async def execute_sql(self, query: str, workspace_id: Optional[str] = None) -> List[dict]:
        return await self._execute_sql_raw(query, workspace_id)
    
    @handle_errors
    async def list_tables(self, schemas: List[str] = None, workspace_id: Optional[str] = None) -> List[dict]:
        if schemas is None:
            schemas = ["public"]

        # 验证 schema 名称，防止 SQL 注入
        for schema in schemas:
            if not schema.replace('_', '').isalnum():
                raise ValueError(f"Invalid schema name: {schema}")

        schema_list = "', '".join(schemas)
        query = f"""
        SELECT
            schemaname as schema,
            tablename as name
        FROM pg_tables
        WHERE schemaname IN ('{schema_list}')
        ORDER BY schemaname, tablename
        """

        return await self._execute_sql_raw(query, workspace_id)
    
    @handle_errors
    async def list_migrations(self, workspace_id: Optional[str] = None) -> List[dict]:
        query = """
        CREATE SCHEMA IF NOT EXISTS supabase_migrations;
        CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
            version text PRIMARY KEY,
            name text NOT NULL,
            inserted_at timestamptz NOT NULL DEFAULT now()
        );
        SELECT version, name
        FROM supabase_migrations.schema_migrations
        ORDER BY version DESC
        """
        return await self._execute_sql_raw(query, workspace_id)

    @handle_errors
    async def list_extensions(self, workspace_id: Optional[str] = None) -> List[dict]:
        query = """
        SELECT
            e.extname AS name,
            n.nspname AS schema,
            e.extversion AS version
        FROM pg_extension e
        JOIN pg_namespace n ON n.oid = e.extnamespace
        ORDER BY e.extname
        """
        return await self._execute_sql_raw(query, workspace_id)
    
    @handle_errors
    @read_only_check
    async def apply_migration(self, name: str, query: str, workspace_id: Optional[str] = None) -> dict:
        if not name or not name.strip():
            raise ValueError("Migration name cannot be empty")
        if not query or not query.strip():
            raise ValueError("Migration SQL cannot be empty")

        migration_name = name.strip().replace("'", "''")
        migration_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        migration_sql = f"""
        BEGIN;
        CREATE SCHEMA IF NOT EXISTS supabase_migrations;
        CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
            version text PRIMARY KEY,
            name text NOT NULL,
            inserted_at timestamptz NOT NULL DEFAULT now()
        );
        {query}
        INSERT INTO supabase_migrations.schema_migrations (version, name)
        VALUES ('{migration_version}', '{migration_name}')
        ON CONFLICT (version) DO UPDATE SET name = EXCLUDED.name;
        COMMIT;
        """
        await self._execute_sql_raw(migration_sql, workspace_id)
        return {
            "success": True,
            "message": f"Migration {name} applied successfully",
            "version": migration_version,
            "name": name.strip(),
        }

    def _to_ts_type(self, data_type: str, udt_name: str) -> str:
        normalized_data_type = (data_type or "").lower()
        normalized_udt_name = (udt_name or "").lower()
        if normalized_data_type in {"smallint", "integer", "bigint", "numeric", "decimal", "real", "double precision"}:
            return "number"
        if normalized_data_type in {"boolean"}:
            return "boolean"
        if normalized_data_type in {"json", "jsonb"}:
            return "Json"
        if normalized_data_type in {"date", "timestamp without time zone", "timestamp with time zone", "time without time zone", "time with time zone"}:
            return "string"
        if normalized_data_type in {"bytea"}:
            return "string"
        if normalized_data_type == "array":
            base = normalized_udt_name[1:] if normalized_udt_name.startswith("_") else normalized_udt_name
            item_type = self._to_ts_type(base, base)
            return f"{item_type}[]"
        if normalized_udt_name in {"uuid", "varchar", "text", "bpchar", "name", "citext", "inet"}:
            return "string"
        if normalized_udt_name in {"int2", "int4", "int8", "float4", "float8"}:
            return "number"
        if normalized_udt_name in {"bool"}:
            return "boolean"
        if normalized_udt_name in {"json", "jsonb"}:
            return "Json"
        return "string"

    def _to_ts_key(self, key: str) -> str:
        if key.replace("_", "").isalnum() and not key[0].isdigit():
            return key
        escaped = key.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    @handle_errors
    async def generate_typescript_types(
        self,
        schemas: List[str] = None,
        workspace_id: Optional[str] = None
    ) -> str:
        if schemas is None:
            schemas = ["public"]
        for schema in schemas:
            if not schema.replace('_', '').isalnum():
                raise ValueError(f"Invalid schema name: {schema}")

        schema_list = "', '".join(schemas)
        query = f"""
        SELECT
            table_schema,
            table_name,
            column_name,
            is_nullable,
            is_identity,
            data_type,
            udt_name,
            column_default
        FROM information_schema.columns
        WHERE table_schema IN ('{schema_list}')
        ORDER BY table_schema, table_name, ordinal_position
        """
        columns = await self._execute_sql_raw(query, workspace_id)

        grouped: dict[str, dict[str, list[dict]]] = {}
        for column in columns:
            schema_name = column.get("table_schema")
            table_name = column.get("table_name")
            grouped.setdefault(schema_name, {})
            grouped[schema_name].setdefault(table_name, [])
            grouped[schema_name][table_name].append(column)

        lines: list[str] = []
        lines.append("export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]")
        lines.append("")
        lines.append("export type Database = {")

        for schema_name in sorted(grouped.keys()):
            tables = grouped[schema_name]
            lines.append(f"  {self._to_ts_key(schema_name)}: {{")
            lines.append("    Tables: {")

            for table_name in sorted(tables.keys()):
                table_columns = tables[table_name]
                lines.append(f"      {self._to_ts_key(table_name)}: {{")
                lines.append("        Row: {")
                for column in table_columns:
                    col_name = column.get("column_name")
                    ts_key = self._to_ts_key(col_name)
                    base_type = self._to_ts_type(column.get("data_type", ""), column.get("udt_name", ""))
                    nullable = column.get("is_nullable") == "YES"
                    row_type = f"{base_type} | null" if nullable else base_type
                    lines.append(f"          {ts_key}: {row_type}")
                lines.append("        }")
                lines.append("        Insert: {")
                for column in table_columns:
                    col_name = column.get("column_name")
                    ts_key = self._to_ts_key(col_name)
                    base_type = self._to_ts_type(column.get("data_type", ""), column.get("udt_name", ""))
                    nullable = column.get("is_nullable") == "YES"
                    has_default = column.get("column_default") is not None
                    is_identity = column.get("is_identity") == "YES"
                    optional = nullable or has_default or is_identity
                    insert_type = f"{base_type} | null" if nullable else base_type
                    suffix = "?" if optional else ""
                    lines.append(f"          {ts_key}{suffix}: {insert_type}")
                lines.append("        }")
                lines.append("        Update: {")
                for column in table_columns:
                    col_name = column.get("column_name")
                    ts_key = self._to_ts_key(col_name)
                    base_type = self._to_ts_type(column.get("data_type", ""), column.get("udt_name", ""))
                    nullable = column.get("is_nullable") == "YES"
                    update_type = f"{base_type} | null" if nullable else base_type
                    lines.append(f"          {ts_key}?: {update_type}")
                lines.append("        }")
                lines.append("      }")

            lines.append("    }")
            lines.append("    Views: {}")
            lines.append("    Functions: {}")
            lines.append("    Enums: {}")
            lines.append("    CompositeTypes: {}")
            lines.append("  }")

        lines.append("}")
        return "\n".join(lines)
