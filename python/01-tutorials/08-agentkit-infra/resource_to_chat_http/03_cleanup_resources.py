#!/usr/bin/env python3
"""清理 RuntimeTemplate、Environment 及关联资源，并归档 Harness。"""

from _clients import TopClient
from _common import emit, load_state, parser, run
from _config import clear_runtime_values, validated_config
from _curl import clear_session_curl_scripts
from _workflow import cleanup_resources


def main() -> None:
    cli = parser(__doc__)
    args = cli.parse_args()
    if args.dry_run:
        emit(
            "dry_run",
            "控制面清理计划",
            json_output=args.json_output,
            actions=[
                "检查 Session / 清理残留 API Key",
                "DeleteRuntimeTemplate / 等待删除完成",
                "DeleteSessionStore / 等待删除完成",
                "清理 Environment 及本次记录的关联资源",
                "ArchiveHarness",
                "retain Endpoint",
                "清空 YAML 运行时配置和两个 curl 脚本的连接配置",
            ],
            status="dry_run（未查询资源，名称和 ID 未获取）",
        )
        return
    config = validated_config(require_model_key_name=False)
    try:
        client = TopClient(config.control)
        state = load_state(client)
        cleanup_resources(
            client,
            state,
            environment_api_key=config.environment.env_api_key_value,
            json_output=args.json_output,
        )
    finally:
        try:
            clear_runtime_values()
        finally:
            clear_session_curl_scripts()


if __name__ == "__main__":
    run(main)
