"""调用 CreateRuntimeTemplate 创建由服务管理的 AGENTKIT Runtime 模板。"""

from __future__ import annotations

import os

from _common import (
    event,
    json_object,
    parser,
    poll_template,
    positive_int,
    run,
    save_state,
    string_map,
    validate_template,
)
from _config import activate_control, load_config
from _http_client import RuntimeTemplateHttpClient
from _iam_roles import prepare_runtime_role


def main() -> None:
    config = load_config()
    template = config.runtime_template
    args_parser = parser("创建 RuntimeTemplate", mutation=True)
    args_parser.add_argument(
        "--name",
        default=template.generated_name(),
        help="账号内唯一模板名；默认按 YAML name_prefix 自动生成",
    )
    args_parser.add_argument(
        "--description",
        default=template.description,
        help="模板描述",
    )
    args_parser.add_argument(
        "--role-name",
        default=os.getenv("AGENTKIT_RUNTIME_ROLE_NAME", "") or template.role_name,
        help="预先创建的 Runtime Role；环境变量可覆盖 YAML",
    )
    args_parser.add_argument(
        "--image-url",
        default=template.image_url,
        help="Runtime 镜像 tag 或 digest",
    )
    args_parser.add_argument(
        "--cpu-milli",
        type=positive_int,
        default=template.cpu_milli,
    )
    args_parser.add_argument(
        "--memory-mib",
        type=positive_int,
        default=template.memory_mib,
    )
    args_parser.add_argument(
        "--min-replicas",
        type=positive_int,
        default=template.min_replicas,
    )
    args_parser.add_argument(
        "--max-replicas",
        type=positive_int,
        default=template.max_replicas,
    )
    args_parser.add_argument(
        "--envs",
        type=json_object,
        default=template.envs,
        help="普通配置 JSON 对象；禁止放入密钥",
    )
    args_parser.add_argument(
        "--meta",
        type=json_object,
        default=template.meta,
        help="字符串元数据 JSON 对象",
    )
    args_parser.add_argument("--port", type=positive_int, default=template.port)
    args_parser.add_argument(
        "--session-store-id",
        default=os.getenv("AGENTKIT_SESSION_STORE_ID", "") or template.session_store_id,
        help="引用已 Ready 的账号级 SessionStore（新模板必需）",
    )
    args_parser.add_argument(
        "--start-command",
        default=template.start_command,
        choices=(
            "bash /app/run-runtime.sh",
            "python /app/examples/16_self_host_sandbox/agentkit_runtime.py",
            "bash /app/examples/16_self_host_sandbox/run-runtime.sh",
        ),
    )
    args = args_parser.parse_args()
    activate_control(config, require_credentials=not args.dry_run)
    if not args.session_store_id and not args.dry_run:
        raise RuntimeError(
            "Set --session-store-id or runtime_template.session_store_id before creating a template"
        )
    if args.session_store_id and any(
        name.upper().startswith(("DATABASE_POSTGRESQL_", "DATABASE_MYSQL_"))
        for name in args.envs
    ):
        raise RuntimeError("SessionStoreId cannot be combined with database Envs")

    if args.min_replicas > args.max_replicas:
        raise RuntimeError("--max-replicas must be >= --min-replicas")
    if (args.port is None) != (args.start_command is None):
        raise RuntimeError("--port and --start-command must be supplied together")
    role_name, role_reused = prepare_runtime_role(
        args.role_name or None,
        dry_run=args.dry_run,
    )

    body = {
        "Name": args.name,
        "RoleName": role_name,
        "Resources": {
            "CpuMilli": args.cpu_milli,
            "MemoryMiB": args.memory_mib,
            "MinReplicas": args.min_replicas,
            "MaxReplicas": args.max_replicas,
        },
        "Envs": string_map(args.envs, "Envs"),
        "Meta": string_map(args.meta, "Meta"),
        "ClientToken": args.client_token,
    }
    if args.session_store_id:
        body["SessionStoreId"] = args.session_store_id
    if args.description is not None:
        body["Description"] = args.description
    if args.image_url is not None:
        body["ImageUrl"] = args.image_url
    if args.port is not None:
        body["Runtime"] = {
            "Port": args.port,
            "StartCommand": args.start_command,
        }

    action = "CreateRuntimeTemplate"
    event(
        action,
        "dry-run" if args.dry_run else "request",
        body,
        json_output=args.json_output,
    )
    if args.dry_run:
        return
    if not args.json_output:
        operation = "复用" if role_reused else "创建"
        print(f"[IAM] 已{operation} Runtime Role：{role_name}")
    client = RuntimeTemplateHttpClient()
    response = validate_template(client.call(action, body))
    config_file = save_state(response)
    if args.wait and response["Status"] != "Ready":
        response = poll_template(client, response["RuntimeTemplateId"], wanted="Ready")
        save_state(response)
    event(
        action,
        "response",
        body,
        response=response,
        json_output=args.json_output,
    )
    if not args.json_output:
        print(f"配置文件: {config_file}")


if __name__ == "__main__":
    run(main)
