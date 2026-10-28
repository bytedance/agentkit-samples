"""终端展示；常规事件已脱敏，专用 SelfHosted 连接输出按要求显示明文。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from rich import box
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(markup=False, highlight=False)
error_console = Console(stderr=True, markup=False, highlight=False)
_shown_parameters: dict[tuple[str, str], dict[str, Any]] = {}


def display_selfhost_connection(connection: dict[str, str]) -> None:
    """在最后单独高亮连接配置，保持每行变量完整，便于复制。"""
    console.print()
    console.rule(
        Text("SelfHosted 连接配置", style="bold bright_cyan"), style="bright_cyan"
    )
    for name, value in connection.items():
        line = Text(f"{name}=", style="bold bright_cyan")
        line.append(value, style="bold bright_green")
        console.print(line, soft_wrap=True)
    console.rule(style="bright_cyan")


LABELS = {
    "name": "名称",
    "id": "ID",
    "title": "标题",
    "result": "处理",
    "state_file": "状态文件",
    "run_id": "运行 ID",
    "next_step": "下一步",
    "agent_loop": "Agent Loop",
    "model_id": "模型",
    "model_base_url": "模型地址",
    "base_url": "访问地址",
    "role_name": "执行角色",
    "version": "版本",
    "reused": "复用已有资源",
    "Type": "类型",
    "CpuMilli": "CPU (milli)",
    "MemoryMb": "内存 (MB)",
    "MemoryMiB": "内存 (MiB)",
    "MinReplicas": "最小副本数",
    "MaxReplicas": "最大副本数",
    "environment": "Environment",
    "endpoint": "Endpoint",
    "harness": "Harness",
    "runtime_template": "RuntimeTemplate",
    "runtime_type": "运行时类型",
    "ark_api_key_name": "模型 Key 名称",
    "event_id": "事件 ID",
    "event_type": "事件类型",
    "tool_name": "工具",
    "tool_use_id": "调用 ID",
    "stop_reason": "结束原因",
    "expected_substring": "预期回复包含",
    "revision": "修订版本",
    "desired_generation": "目标版本",
    "observed_generation": "已应用版本",
    "details": "详情",
    "sequence": "事件序号",
}

STATUSES = {
    "reused": ("已复用", "green"),
    "created": ("已创建", "green"),
    "ready": ("就绪", "green"),
    "active": ("可用", "green"),
    "idle": ("空闲", "green"),
    "deleted": ("已删除", "green"),
    "archived": ("已归档", "green"),
    "not_found": ("不存在", "dim"),
    "resources_ready": ("资源全部就绪", "green"),
    "cleaned": ("清理完成", "green"),
    "chat_completed": ("对话完成", "green"),
    "completed": ("执行成功", "green"),
    "initializing": ("初始化", "cyan"),
    "building": ("构建中", "yellow"),
    "creating": ("创建中", "yellow"),
    "deleting": ("删除中", "yellow"),
    "failed": ("失败", "red"),
    "deletefailed": ("删除失败", "red"),
}


def status_text(value: Any) -> Text:
    raw = str(value)
    label, style = STATUSES.get(raw.lower(), (raw, "dim"))
    marker = "✓" if style == "green" else "×" if style == "red" else "·"
    return Text(f"{marker} {label}", style=style)


def progress_text(description: str, status: Any = None) -> Text:
    text = Text(f"  {description}…", style="cyan")
    if status is not None:
        text.append("  ")
        text.append_text(status_text(status))
    return text


def _value(value: Any, *, style: str = "") -> Text:
    if isinstance(value, bool):
        value = "是" if value else "否"
    elif isinstance(value, list):
        value = "、".join(str(item) for item in value) if value else "无"
    return Text(str(value), style=style, overflow="fold")


def _rows(fields: dict[str, Any]) -> Iterator[tuple[str, Text]]:
    for key, value in fields.items():
        if value is None:
            continue
        label = LABELS.get(key, key)
        if isinstance(value, dict):
            if "id" in value:
                identity = Text(overflow="fold")
                if value.get("name"):
                    identity.append(str(value["name"]) + "\n", style="dim")
                identity.append(str(value["id"]), style="cyan")
                yield label, identity
            else:
                yield from _rows(value)
        else:
            yield label, _value(value, style="cyan" if key.endswith("id") else "")


def _fields(fields: dict[str, Any]) -> None:
    if not fields:
        return
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", width=16, overflow="fold")
    table.add_column(overflow="fold")
    for label, value in _rows(fields):
        table.add_row(label, value)
    console.print(Padding(table, (0, 2), expand=False))


def _resource(fields: dict[str, Any]) -> None:
    title = Text(str(fields["resource"]), style="bold")
    if fields.get("status"):
        title.append("  ")
        title.append_text(status_text(fields["status"]))
    console.print(Padding(title, (0, 2), expand=False))
    _fields({key: fields[key] for key in ("name", "id", "title") if fields.get(key)})
    identity = (str(fields["resource"]), str(fields.get("id", "")))
    previous = _shown_parameters.setdefault(identity, {})
    parameters = fields.get("parameters") or {}
    changed = {
        key: value
        for key, value in parameters.items()
        if key not in previous or previous[key] != value
    }
    if changed:
        label = "本步参数" if previous else "核心配置"
        console.print(Padding(Text(label, style="dim"), (1, 2, 0, 2), expand=False))
        _fields(changed)
        previous.update(parameters)
    status_label = STATUSES.get(str(fields.get("status", "")).lower(), ("", ""))[0]
    if fields.get("result") and fields["result"] != status_label:
        console.print(
            Padding(Text(str(fields["result"]), style="dim"), (0, 2), expand=False)
        )


def _summary(resources: list[dict[str, Any]]) -> None:
    # Name and ID share a column so complete identifiers fit ordinary 80-column terminals.
    table = Table(
        box=box.SIMPLE_HEAD,
        expand=True,
        padding=(0, 1),
        leading=1,
        header_style="bold",
        border_style="dim",
        pad_edge=False,
    )
    table.add_column("资源", max_width=19, overflow="fold", style="bold")
    table.add_column("名称 / ID", ratio=1, overflow="fold")
    table.add_column("状态 / 处理", max_width=14, overflow="fold")
    for item in resources:
        identity = Text(overflow="fold")
        if item.get("name"):
            identity.append(str(item["name"]) + "\n")
        identity.append(str(item.get("id") or "未记录"), style="cyan")
        if item.get("title"):
            identity.append("\n" + str(item["title"]), style="dim")
        status = status_text(item.get("status", "未记录"))
        if item.get("result"):
            status.append("\n" + str(item["result"]), style="dim")
        table.add_row(Text(str(item.get("resource", ""))), identity, status)
    console.print(Padding(table, (0, 2)))


def _tool_result_text(value: Any) -> str:
    """展开纯文本内容块；其他结构保留为 JSON。"""
    raw = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    )
    try:
        blocks = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if (
        isinstance(blocks, list)
        and blocks
        and all(
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
            for block in blocks
        )
    ):
        return (
            "\n".join(block["text"].rstrip() for block in blocks).strip() or "<empty>"
        )
    return raw


def _verification(fields: dict[str, Any]) -> None:
    checks = fields["verification"]
    tools = fields.get("tool_names") or []
    required = checks.get("required_tools") or []
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", width=12)
    table.add_column(overflow="fold")
    table.add_row("Session", _value(fields["id"], style="cyan"))
    # table.add_row("本轮耗时", Text(f"{checks['elapsed_seconds']:.1f} 秒"))
    table.add_row("本轮结束", Text(checks["stop_reason"]))
    if required:
        passed = sum(name in tools for name in required)
        table.add_row("工具覆盖", Text(f"{passed} / {len(required)} 项通过"))
    else:
        table.add_row("成功工具", Text(f"{len(tools)} 项（未启用覆盖校验）"))
    if tools:
        ordered = [name for name in required if name in tools]
        ordered.extend(name for name in tools if name not in ordered)
        table.add_row(
            "", Text("   ".join(f"✓ {name}" for name in ordered), style="green")
        )
    expected = checks.get("expected_substring")
    table.add_row(
        "回复校验",
        Text(
            "✓ 包含预期文本" if expected else "未设置预期文本",
            style="green" if expected else "dim",
        ),
    )
    if expected and expected != fields["answer"].strip():
        table.add_row("预期文本", _value(expected))
    table.add_row("", Text(""))
    table.add_row("智能体回复", _value(fields["answer"], style="bold"))
    console.print(
        Padding(
            Panel(
                table,
                title=Text("验证结果", style="bold green"),
                title_align="left",
                border_style="green",
                box=box.ROUNDED,
                padding=(1, 2),
            ),
            (0, 2),
        )
    )


def display_event(
    phase: str, message: str, fields: dict[str, Any], *, step: int | None, heading: bool
) -> None:
    if phase == "poll":
        line = Text("  · " + message, style="dim")
        if fields.get("status"):
            line.append("  ")
            line.append_text(status_text(fields["status"]))
        console.print(line)
        return
    if phase == "tool_result":
        status = status_text(fields.get("status", "completed"))
        line = Text(
            f"  {step or 0:02d}  {fields.get('tool_name') or 'unknown'}  ",
            style="bold",
        )
        line.append_text(status)
        console.print(line)
        if fields.get("result") is not None:
            content = (fields.get("raw_result") or {}).get("content", fields["result"])
            summary = _tool_result_text(content).strip()
            summary = (
                summary.replace("\r\n", "\n")
                .replace("\r", r"\r")
                .replace("\n", r"\n")
                .replace("\t", r"\t")
            )
            if len(summary) > 500:
                summary = summary[:500] + "…"
            output = Text("↳ 工具输出  ", style="bold cyan", overflow="fold")
            output.append(summary, style="bold default")
            console.print(
                Padding(
                    output,
                    (0, 4),
                    expand=False,
                )
            )
        if "raw_result" in fields:
            raw = json.dumps(
                fields["raw_result"], ensure_ascii=False, separators=(",", ":")
            )
            console.print(
                Padding(
                    Panel(
                        Text(raw, style="dim", overflow="fold"),
                        title=Text("原始事件 · JSON", style="dim"),
                        title_align="left",
                        border_style="dim",
                        box=box.ROUNDED,
                        padding=(0, 1),
                    ),
                    (0, 4),
                )
            )
        return
    if heading:
        console.print()
        title = Text(
            f"{step:02d}  {message}" if step is not None else message, style="bold cyan"
        )
        console.rule(title, align="left", style="dim")
        console.print()
    if phase == "verified" and "verification" in fields:
        _verification(fields)
        return
    if fields.get("resource"):
        _resource(fields)
    elif "resources" in fields:
        _summary(fields["resources"])
    else:
        ordinary = {
            k: v
            for k, v in fields.items()
            if k not in {"actions", "parameters", "status", "prompt", "answer"}
        }
        _fields({**ordinary, **(fields.get("parameters") or {})})
        if fields.get("status"):
            console.print(Padding(status_text(fields["status"]), (0, 2)))
    for index, action in enumerate(fields.get("actions", []), 1):
        console.print(Text(f"  {index:02d}  {action}"))
    if "resources" in fields and fields.get("next_step"):
        _fields({"next_step": fields["next_step"]})
    for key, label, color in (
        ("prompt", "问 · 用户", "blue"),
        ("answer", "答 · 助手", "green"),
    ):
        if key in fields:
            console.print(
                Padding(
                    Panel(
                        _value(fields[key]),
                        title=Text(label),
                        title_align="left",
                        border_style=color,
                        box=box.ROUNDED,
                        padding=(0, 1),
                    ),
                    (0, 2),
                )
            )


def display_error(message: str) -> None:
    # Plain text objects prevent returned names, prompts, or errors being parsed as markup.
    error_console.print(Text("\n错误  " + message, style="bold red"), soft_wrap=True)
