"""在线验收：真实工具结果到达后立即删除会话，测量异步回收时序。"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.sample import (  # noqa: E402
    configure_paths,
    key_path,
    restore_run_config,
)
from common.stream import run_queue_sse  # noqa: E402
from common.clients import DataPlaneClient, HarnessInfraError, TopClient  # noqa: E402
from common.state import load_state, save_state, state_path, update_resource  # noqa: E402
from common.config import validated_config  # noqa: E402
from common.workflow import _not_found  # noqa: E402


def write_report(path, report):
    """原子保存不含凭据的验收时间线；恢复执行时不重复发送模型消息。"""
    temporary = path.with_suffix(".tmp")
    with os.fdopen(
        os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
    ) as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
        out.write("\n")
    temporary.replace(path)


def stamp(report, name, **details):
    """以 UTC 和单调计时同时记录一次观测，区分请求发出与响应返回。"""
    row = {
        "name": name,
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "monotonic": time.monotonic(),
        **details,
    }
    report["timeline"].append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row


def command(step):
    """沿用 README 的公开入口，步骤失败即停，保留本轮资源供清理。"""
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("run.py")), step], check=True
    )


def main():
    """仅使用全新、独占的 Queue Cloud 轮次；恢复模式只继续回收观测。"""
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--timeout", type=int, default=1200, help="回收观测上限，秒")
    cli.add_argument("--interval", type=float, default=3, help="轮询间隔，秒")
    cli.add_argument(
        "--resume", action="store_true", help="续测原轮次，不再发送工具消息"
    )
    args = cli.parse_args()
    if args.timeout <= 0 or args.interval <= 0:
        cli.error("--timeout 和 --interval 必须大于零")
    configure_paths("queue-cloud")
    report_path = state_path().with_name("tool-delete-acceptance.json")
    if args.resume:
        report = json.loads(report_path.read_text())
        report["status"] = "running"
        report.pop("error_type", None)
    else:
        if state_path().exists() and not load_state().get("cleaned"):
            raise RuntimeError(
                "已有未清理 Queue Cloud 轮次，请先 cleanup 或使用 --resume"
            )
        for step in (
            "create-route",
            "create-environment",
            "create-harness",
            "create-session-store",
            "create-runtime-template",
            "create-api-key",
            "create-session",
        ):
            command(step)
        report = {
            "status": "running",
            "marker": "TOOL_DELETE_" + uuid.uuid4().hex,
            "timeline": [],
            "polls": [],
            "poll_interval_seconds": args.interval,
        }
    state = load_state()
    if state.get("sample_mode") != "queue-cloud" or state.get("cleaned"):
        raise RuntimeError("验收轮次已清理或不属于 Queue Cloud")
    resources = state["resources"]
    sandbox = resources["environment_resource"]
    if not sandbox.get("owned") or not resources["session"].get("owned"):
        raise RuntimeError("只允许删除本轮独占的会话和 Sandbox 资源")
    if args.resume and report.get("run_id") != state["run_id"]:
        raise RuntimeError("报告不属于当前轮次")
    report.update(
        run_id=state["run_id"],
        session_id=resources["session"]["id"],
        resource_id=sandbox["id"],
    )
    config = validated_config(require_model_key_name=False)
    top = TopClient(config.control)
    config = restore_run_config(config, top, state)
    if not config.environment.env_api_key_value:
        raise RuntimeError("本轮 Environment API Key 不可用")
    data = DataPlaneClient(
        resources["endpoint"]["base_url"], config.environment.env_api_key_value
    )
    session_path = "/v1/sessions/" + report["session_id"]

    def persist():
        """写入当前验收进度，异常退出后保留全部已观测时间点。"""
        write_report(report_path, report)

    def seen(name):
        """查询持久化里程碑，防止恢复模式重复登记首次观测。"""
        return next((row for row in report["timeline"] if row["name"] == name), None)

    def delete_session():
        """工具成功后直接 DELETE，不等模型最终回复，也不预先 archive。"""
        state["cleanup_started"] = True
        save_state(state)
        stamp(report, "session_delete_sent")
        persist()
        try:
            reply = data.call("DELETE", session_path)
            if reply.get("type") != "session_deleted":
                raise RuntimeError("DELETE 未返回 session_deleted")
            stamp(report, "session_delete_accepted", response_type=reply["type"])
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise
            stamp(report, "session_delete_already_absent", http_status=404)
        persist()

    try:
        if not args.resume:
            calls = set()
            marker = report["marker"]

            def observe(event):
                """只接受本轮命令的匹配工具结果，模型复述标记不算成功。"""
                if event.get("type") == "agent.tool_use":
                    if event.get("name", "").lower() in (
                        "bash",
                        "execute",
                    ) and marker in json.dumps(event.get("input")):
                        calls.add(event.get("id"))
                if (
                    event.get("type") == "user.tool_result"
                    and event.get("tool_use_id") in calls
                    and event.get("is_error") is False
                    and marker in json.dumps(event.get("content"))
                ):
                    stamp(
                        report, "tool_result_received", tool_use_id=event["tool_use_id"]
                    )
                    delete_session()
                    return True
                return False

            persist()
            run_queue_sse(
                data.base_url,
                data.api_key,
                report["session_id"],
                f"必须用 bash 执行 echo {marker}，不要模拟工具结果，只回复实际输出。",
                on_event=observe,
            )
            if not seen("tool_result_received"):
                raise RuntimeError("没有收到匹配的成功工具结果，未执行验收删除")
        elif not seen("tool_result_received"):
            raise RuntimeError("尚未验证真实工具结果，不能恢复删除验收")
        elif not seen("session_delete_accepted") and not seen(
            "session_delete_already_absent"
        ):
            delete_session()

        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            poll = {"utc": dt.datetime.now(dt.timezone.utc).isoformat()}
            if not seen("session_first_404"):
                try:
                    response = data.call("GET", session_path)
                    poll["session_status"] = response.get("status")
                except HarnessInfraError as exc:
                    if not _not_found(exc):
                        raise
                    stamp(report, "session_first_404", http_status=404)
                    update_resource(state, "session", {"status": "deleted"})
            if not seen("resource_delete_accepted"):
                try:
                    top.call(
                        "DeleteEnvironmentResource",
                        {
                            "ResourceId": sandbox["id"],
                            "ClientToken": state["tokens"]["resource_delete"],
                        },
                    )
                    stamp(
                        report,
                        "resource_delete_accepted",
                        session_404_observed=bool(seen("session_first_404")),
                    )
                except HarnessInfraError as exc:
                    if exc.status_code == 409 and exc.code == "ResourceInUse":
                        poll["resource_delete_status"] = "409 ResourceInUse"
                        if not seen("resource_first_409"):
                            stamp(
                                report, "resource_first_409", request_id=exc.request_id
                            )
                    else:
                        raise
            if seen("resource_delete_accepted") and not seen("resource_deleted"):
                try:
                    response = top.call(
                        "GetEnvironmentResource", {"ResourceId": sandbox["id"]}
                    )
                    poll["resource_status"] = response.get("Status")
                    deleted = response.get("Status") == "Deleted"
                    if response.get("Status") in ("Failed", "DeleteFailed"):
                        raise RuntimeError("Sandbox 资源删除失败")
                except HarnessInfraError as exc:
                    if not _not_found(exc):
                        raise
                    deleted = True
                if deleted:
                    stamp(report, "resource_deleted")
                    update_resource(
                        state, "environment_resource", {"status": "Deleted"}
                    )
            report["polls"].append(poll)
            persist()
            if seen("session_first_404") and seen("resource_deleted"):
                break
            time.sleep(args.interval)
        else:
            raise TimeoutError("回收超时，保留状态和 Key；可用 --resume 继续观测")
        report["timing_seconds"] = {
            name: round(
                seen(name)["monotonic"] - seen("tool_result_received")["monotonic"], 3
            )
            for name in (
                "session_delete_sent",
                "session_delete_accepted",
                "session_first_404",
                "resource_delete_accepted",
                "resource_deleted",
            )
            if seen(name)
        }
        ordered = seen("resource_delete_accepted")["session_404_observed"]
        command("cleanup")
        report["cleanup_completed"] = (
            load_state().get("cleaned") and not key_path().exists()
        )
        report["status"] = (
            "passed" if ordered and report["cleanup_completed"] else "failed_order"
        )
        persist()
        if not ordered:
            raise RuntimeError("资源删除受理早于会话 404 观测，详见验收报告")
        print(f"验收通过：{report_path}", flush=True)
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        if report["status"] == "running":
            report["status"] = "incomplete"
        persist()
        print(f"验收未通过；证据保存在 {report_path}", flush=True)
        raise


if __name__ == "__main__":
    main()
