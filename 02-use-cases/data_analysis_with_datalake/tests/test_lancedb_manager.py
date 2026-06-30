from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "lancedb_manager.py"


class FakeConsole:
    def print(self, *args, **kwargs):
        return None


class FakeDuckDBConnection:
    pass


class FakeDuckDB:
    DuckDBPyConnection = FakeDuckDBConnection

    def __init__(self):
        self.connections = 0

    def connect(self):
        self.connections += 1
        return FakeDuckDBConnection()


class FakeDB:
    def __init__(self):
        self.opened_tables = []

    def open_table(self, table_name):
        self.opened_tables.append(table_name)
        return {"table": table_name}


class FakeLanceDB:
    def __init__(self):
        self.calls = []
        self.db = FakeDB()

    def connect(self, uri, storage_options=None):
        self.calls.append((uri, storage_options))
        return self.db


def load_module(monkeypatch):
    rich = types.ModuleType("rich")
    rich_console = types.ModuleType("rich.console")
    rich_console.Console = FakeConsole
    fake_duckdb = FakeDuckDB()
    fake_lancedb = FakeLanceDB()
    monkeypatch.setitem(sys.modules, "rich", rich)
    monkeypatch.setitem(sys.modules, "rich.console", rich_console)
    monkeypatch.setitem(sys.modules, "duckdb", fake_duckdb)
    monkeypatch.setitem(sys.modules, "lancedb", fake_lancedb)

    spec = importlib.util.spec_from_file_location("datalake_lancedb_manager", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, fake_lancedb, fake_duckdb


def test_split_db_and_table_supports_s3_and_tos(monkeypatch):
    module, _, _ = load_module(monkeypatch)
    manager = module.LanceDBManager()

    assert manager._split_db_and_table("s3://bucket/root/table") == (
        "s3://bucket/root",
        "table",
    )
    assert manager._split_db_and_table("tos://bucket/root/table") == (
        "tos://bucket/root",
        "table",
    )
    assert manager._split_db_and_table("") == (None, None)


def test_storage_options_builds_volcengine_endpoint(monkeypatch):
    module, _, _ = load_module(monkeypatch)
    manager = module.LanceDBManager()
    manager.tos_region = "cn-shanghai"

    options = manager._storage_options("s3://demo-bucket/path/table")

    assert options["aws_endpoint"] == "https://demo-bucket.tos-s3-cn-shanghai.volces.com"
    assert options["virtual_hosted_style_request"] == "true"
    assert options["skip_signature"] == "true"


def test_storage_options_respects_explicit_endpoint(monkeypatch):
    module, _, _ = load_module(monkeypatch)
    manager = module.LanceDBManager()
    manager.lancedb_aws_endpoint = "https://custom.example.com"

    options = manager._storage_options("s3://demo-bucket/path/table")

    assert options["aws_endpoint"] == "https://custom.example.com"


def test_open_table_rejects_missing_or_local_uri(monkeypatch):
    module, _, _ = load_module(monkeypatch)
    manager = module.LanceDBManager()

    table, error = manager.open_table(uri="/tmp/local-table")

    assert table is None
    assert "LANCEDB_URI" in error


def test_open_table_caches_connection_and_table(monkeypatch):
    module, fake_lancedb, _ = load_module(monkeypatch)
    manager = module.LanceDBManager()

    first, first_error = manager.open_table(uri="s3://bucket/root/table")
    second, second_error = manager.open_table(uri="s3://bucket/root/table")

    assert first_error is None
    assert second_error is None
    assert first == {"table": "table"}
    assert second is first
    assert len(fake_lancedb.calls) == 1


def test_duckdb_connection_is_cached(monkeypatch):
    module, _, fake_duckdb = load_module(monkeypatch)
    manager = module.LanceDBManager()

    first = manager.get_duckdb_connection()
    second = manager.get_duckdb_connection()

    assert first is second
    assert fake_duckdb.connections == 1
