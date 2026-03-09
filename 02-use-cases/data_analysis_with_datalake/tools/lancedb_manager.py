import os
from typing import Optional, Tuple
from rich.console import Console
import lancedb
import duckdb


console = Console()


class LanceDBManager:
    def __init__(self):
        # Configuration from environment
        self.lancedb_uri = os.getenv(
            "LANCEDB_URI", "s3://emr-serverless-sdk/lance_catalog/default/imdb_top_1000"
        )
        self.lancedb_metadata_uri = os.getenv(
            "LANCEDB_METADATA_URI",
            "s3://emr-serverless-sdk/lance_catalog/default/metadata_table",
        )

        self.tos_region = os.getenv("TOS_REGION", "cn-beijing")
        self.lancedb_aws_endpoint = os.getenv("LANCEDB_AWS_ENDPOINT", "")

        # Cached connections and tables
        self._db_connections = {}
        self._tables = {}
        self._metadata_table = None
        self._duckdb_conn = None

    def _split_db_and_table(self, uri: str) -> Tuple[Optional[str], Optional[str]]:
        """输入形如 s3://bucket/path/.../table_name，返回 (db_root_uri, table_name)。"""
        if not uri:
            return None, None
        scheme = ""
        rest = uri
        if rest.startswith("s3://"):
            scheme = "s3://"
            rest = rest[len("s3://") :]
        elif rest.startswith("tos://"):
            scheme = "tos://"
            rest = rest[len("tos://") :]
        parts = [p for p in rest.split("/") if p]
        if not parts:
            return None, None
        table_name = parts[-1]
        db_root = "/".join(parts[:-1])
        db_root_uri = f"{scheme}{db_root}" if db_root else None
        return db_root_uri, table_name

    def _storage_options(self, uri: str) -> dict:
        """LanceDB storage_options:
        Build storage options for LanceDB connection based on URI and environment variables."""
        endpoint = self.lancedb_aws_endpoint
        if (
            not endpoint
            and uri
            and (uri.startswith("s3://") or uri.startswith("tos://"))
        ):
            no_scheme = uri[len("s3://") :]
            bucket = no_scheme.split("/", 1)[0]
            if bucket:
                endpoint = f"https://{bucket}.tos-s3-{self.tos_region}.volces.com"
        opts = {
            "aws_endpoint": endpoint,
            "virtual_hosted_style_request": "true",
            "aws_unsigned_payload": "true",
            "skip_signature": "true",
        }
        return opts

    def open_table(
        self, table_name: Optional[str] = None, uri: Optional[str] = None
    ) -> Tuple[Optional[object], Optional[str]]:
        """Open and cache a LanceDB table from the given URI or default URI."""
        target_uri = uri or self.lancedb_uri
        cache_key = target_uri + (f":{table_name}" if table_name else "")

        # Return cached table if exists
        if cache_key in self._tables:
            return self._tables[cache_key], None

        if not target_uri or not (
            target_uri.startswith("s3://") or target_uri.startswith("tos://")
        ):
            return (
                None,
                "LanceDB 配置缺失或非法：请在 settings.txt 设置 LANCEDB_URI (s3://...)",
            )

        try:
            db_root_uri, default_table = self._split_db_and_table(target_uri)
            use_table = table_name or default_table

            if not db_root_uri or not use_table:
                return None, "LanceDB URI 非法：无法解析数据库路径与表名"

            # Get or create DB connection
            if db_root_uri not in self._db_connections:
                console.print(f"🚀 初始化 LanceDB 连接: root={db_root_uri}…")
                storage_opts = self._storage_options(target_uri)
                db = lancedb.connect(db_root_uri, storage_options=storage_opts)
                self._db_connections[db_root_uri] = db
            else:
                db = self._db_connections[db_root_uri]

            # Open table
            tbl = db.open_table(use_table)
            console.print(f"   ✅ LanceDB 表 '{use_table}' 连接成功!")

            # Cache the table
            self._tables[cache_key] = tbl
            return tbl, None
        except Exception as e:
            print(e)
            return None, f"连接 LanceDB 失败: {e}"

    def get_metadata_table(self) -> Tuple[Optional[object], Optional[str]]:
        """Open and cache the metadata table."""
        if self._metadata_table is not None:
            return self._metadata_table, None

        tbl, err = self.open_table(uri=self.lancedb_metadata_uri)
        if not err:
            self._metadata_table = tbl
        return tbl, err

    def get_default_table(
        self, table_name: Optional[str] = None
    ) -> Tuple[Optional[object], Optional[str]]:
        """Open and cache the default table."""
        return self.open_table(table_name)

    def get_duckdb_connection(self) -> duckdb.DuckDBPyConnection:
        """Get or create a cached DuckDB connection."""
        if self._duckdb_conn is None:
            self._duckdb_conn = duckdb.connect()
        return self._duckdb_conn


# Create a singleton instance to be used by other modules
lancedb_manager = LanceDBManager()
