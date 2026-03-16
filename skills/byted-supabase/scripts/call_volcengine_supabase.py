#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional


def _bootstrap_env(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--region")
    parser.add_argument("--default-workspace-id")
    parser.add_argument("--read-only", choices=["true", "false"])
    parser.add_argument("--workspace-slug")
    parser.add_argument("--endpoint-scheme")
    known, _ = parser.parse_known_args(argv)
    if known.region:
        os.environ["VOLCENGINE_REGION"] = known.region
    if known.default_workspace_id:
        os.environ["DEFAULT_WORKSPACE_ID"] = known.default_workspace_id
    if known.read_only:
        os.environ["READ_ONLY"] = known.read_only
    if known.workspace_slug:
        os.environ["SUPABASE_WORKSPACE_SLUG"] = known.workspace_slug
    if known.endpoint_scheme:
        os.environ["SUPABASE_ENDPOINT_SCHEME"] = known.endpoint_scheme


_BOOTSTRAP_ARGS = sys.argv[1:]
_bootstrap_env(_BOOTSTRAP_ARGS)

WORKSPACE_ACTIONS = {
    "list-workspaces",
    "describe-workspace",
    "create-workspace",
    "pause-workspace",
    "restore-workspace",
    "get-workspace-url",
    "get-keys",
    "list-branches",
    "create-branch",
    "delete-branch",
    "reset-branch",
}
DATABASE_ACTIONS = {
    "execute-sql",
    "list-tables",
    "list-migrations",
    "list-extensions",
    "apply-migration",
    "generate-typescript-types",
}
EDGE_ACTIONS = {
    "list-edge-functions",
    "get-edge-function",
    "deploy-edge-function",
    "delete-edge-function",
}
STORAGE_ACTIONS = {
    "list-storage-buckets",
    "create-storage-bucket",
    "delete-storage-bucket",
    "get-storage-config",
}


def _read_text(value: Optional[str], file_path: Optional[str], label: str) -> str:
    if value and file_path:
        raise ValueError(f"{label} and {label}-file cannot be used together")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    if value:
        return value
    raise ValueError(f"{label} or {label}-file is required")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="火山引擎 Supabase 本地 CLI（无 MCP 依赖）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("action", help="执行动作")
    parser.add_argument("--region", default=os.getenv("VOLCENGINE_REGION", "cn-beijing"), help="火山引擎地域")
    parser.add_argument("--default-workspace-id", default=os.getenv("DEFAULT_WORKSPACE_ID"), help="默认 workspace ID")
    parser.add_argument("--read-only", choices=["true", "false"], default=os.getenv("READ_ONLY", "false"), help="是否只读")
    parser.add_argument("--workspace-slug", default=os.getenv("SUPABASE_WORKSPACE_SLUG", "default"), help="Edge Functions 项目 slug")
    parser.add_argument("--endpoint-scheme", default=os.getenv("SUPABASE_ENDPOINT_SCHEME", "http"), help="workspace URL 协议")
    parser.add_argument("--workspace-id", help="workspace ID 或 branch ID")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别")

    parser.add_argument("--workspace-name")
    parser.add_argument("--engine-version", default="Supabase_1_24")
    parser.add_argument("--engine-type", default="Supabase")
    parser.add_argument("--name")
    parser.add_argument("--branch-id")
    parser.add_argument("--migration-version")
    parser.add_argument("--reveal", action="store_true")

    parser.add_argument("--query")
    parser.add_argument("--query-file")
    parser.add_argument("--schemas", default="public")

    parser.add_argument("--function-name")
    parser.add_argument("--source-code")
    parser.add_argument("--source-file")
    parser.add_argument("--verify-jwt", dest="verify_jwt", action="store_true", default=True)
    parser.add_argument("--no-verify-jwt", dest="verify_jwt", action="store_false")
    parser.add_argument("--runtime", default="native-node20/v1")
    parser.add_argument("--import-map")
    parser.add_argument("--import-map-file")

    parser.add_argument("--bucket-name")
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--file-size-limit", type=int)
    parser.add_argument("--allowed-mime-types")
    return parser


async def run_action(args: argparse.Namespace) -> str:
    from volcengine_supabase.platform import AidapClient
    from volcengine_supabase.tools.database_tools import DatabaseTools
    from volcengine_supabase.tools.edge_function_tools import EdgeFunctionTools
    from volcengine_supabase.tools.storage_tools import StorageTools
    from volcengine_supabase.tools.workspace_tools import WorkspaceTools

    aidap = AidapClient()
    workspace_tools = WorkspaceTools(aidap, args.default_workspace_id)
    database_tools = DatabaseTools(aidap, args.default_workspace_id)
    edge_tools = EdgeFunctionTools(aidap, args.default_workspace_id)
    storage_tools = StorageTools(aidap, args.default_workspace_id)

    action = args.action
    if action == "list-workspaces":
        return await workspace_tools.list_workspaces()
    if action == "describe-workspace":
        if not args.workspace_id:
            raise ValueError("--workspace-id is required")
        return await workspace_tools.get_workspace(args.workspace_id)
    if action == "create-workspace":
        if not args.workspace_name:
            raise ValueError("--workspace-name is required")
        return await workspace_tools.create_workspace(args.workspace_name, args.engine_version, args.engine_type)
    if action == "pause-workspace":
        return await workspace_tools.pause_workspace(args.workspace_id)
    if action == "restore-workspace":
        return await workspace_tools.restore_workspace(args.workspace_id)
    if action == "get-workspace-url":
        return await workspace_tools.get_workspace_url(args.workspace_id)
    if action == "get-keys":
        return await workspace_tools.get_publishable_keys(args.workspace_id, args.reveal)
    if action == "list-branches":
        return await workspace_tools.list_branches(args.workspace_id)
    if action == "create-branch":
        return await workspace_tools.create_branch(args.name or "develop", args.workspace_id)
    if action == "delete-branch":
        if not args.branch_id:
            raise ValueError("--branch-id is required")
        return await workspace_tools.delete_branch(args.branch_id, args.workspace_id)
    if action == "reset-branch":
        if not args.branch_id:
            raise ValueError("--branch-id is required")
        return await workspace_tools.reset_branch(args.branch_id, args.migration_version, args.workspace_id)

    if action == "execute-sql":
        query = _read_text(args.query, args.query_file, "--query")
        return await database_tools.execute_sql(query, args.workspace_id)
    if action == "list-tables":
        schemas = [schema.strip() for schema in args.schemas.split(",") if schema.strip()]
        return await database_tools.list_tables(schemas, args.workspace_id)
    if action == "list-migrations":
        return await database_tools.list_migrations(args.workspace_id)
    if action == "list-extensions":
        return await database_tools.list_extensions(args.workspace_id)
    if action == "apply-migration":
        if not args.name:
            raise ValueError("--name is required")
        query = _read_text(args.query, args.query_file, "--query")
        return await database_tools.apply_migration(args.name, query, args.workspace_id)
    if action == "generate-typescript-types":
        schemas = [schema.strip() for schema in args.schemas.split(",") if schema.strip()]
        return await database_tools.generate_typescript_types(schemas, args.workspace_id)

    if action == "list-edge-functions":
        return await edge_tools.list_edge_functions(args.workspace_id)
    if action == "get-edge-function":
        if not args.function_name:
            raise ValueError("--function-name is required")
        return await edge_tools.get_edge_function(args.function_name, args.workspace_id)
    if action == "deploy-edge-function":
        if not args.function_name:
            raise ValueError("--function-name is required")
        source_code = _read_text(args.source_code, args.source_file, "--source-code")
        import_map = None
        if args.import_map or args.import_map_file:
            import_map = _read_text(args.import_map, args.import_map_file, "--import-map")
        return await edge_tools.deploy_edge_function(
            args.function_name,
            source_code,
            args.verify_jwt,
            args.runtime,
            import_map,
            args.workspace_id,
        )
    if action == "delete-edge-function":
        if not args.function_name:
            raise ValueError("--function-name is required")
        return await edge_tools.delete_edge_function(args.function_name, args.workspace_id)

    if action == "list-storage-buckets":
        return await storage_tools.list_storage_buckets(args.workspace_id)
    if action == "create-storage-bucket":
        if not args.bucket_name:
            raise ValueError("--bucket-name is required")
        return await storage_tools.create_storage_bucket(
            args.bucket_name,
            args.public,
            args.file_size_limit,
            args.allowed_mime_types,
            args.workspace_id,
        )
    if action == "delete-storage-bucket":
        if not args.bucket_name:
            raise ValueError("--bucket-name is required")
        return await storage_tools.delete_storage_bucket(args.bucket_name, args.workspace_id)
    if action == "get-storage-config":
        return await storage_tools.get_storage_config(args.workspace_id)

    supported = sorted(WORKSPACE_ACTIONS | DATABASE_ACTIONS | EDGE_ACTIONS | STORAGE_ACTIONS)
    raise ValueError(f"Unsupported action: {action}. Available actions: {', '.join(supported)}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s] %(message)s",
    )

    try:
        result = asyncio.run(run_action(args))
        print(result)
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
