"""把共享 YAML 中的模型、MCP 和 Skill 转换为各模式的部署参数。"""

import json
import re
from dataclasses import replace
from urllib.parse import urlsplit

from .config import _read_yaml, _string


MANAGED_ENVS = {
    "MODEL_NAME",
    "MODEL_PROVIDER",
    "MODEL_API_BASE",
    "MODEL_API_KEY",
    "MODEL_AGENT_NAME",
    "MODEL_AGENT_PROVIDER",
    "MODEL_AGENT_API_BASE",
    "MODEL_AGENT_API_KEY",
    "MODEL_AGENT_API_KEY_NAME",
    "SYSTEM_PROMPT",
    "MCP_SERVERS",
    "SKILLS",
    "RUNTIME",
    "HARNESS_SANDBOX_TOOL_ID",
}


def _mcp_servers(entries):
    """校验 Direct 的远程 MCP，并生成 Harness App 配置。

    输入：共享的 name / endpoint / protocol 配置，兼容已有 Name / Type / Url。
    输出：服务定义；支持 Streamable HTTP、SSE 及可选 Bearer API Key。
    异常：重复名称、无效地址及不支持的配置在部署前报错。
    """
    servers, names = [], set()
    aliases = {"Name": "name", "Url": "endpoint", "url": "endpoint", "Type": "type"}
    for index, entry in enumerate(entries):
        label = f"harness.mcp_servers[{index}]"
        if not isinstance(entry, dict):
            raise TypeError(f"{label} 必须是映射")
        server = {}
        for key, value in entry.items():
            normalized = aliases.get(key, key)
            if normalized in server:
                raise RuntimeError(f"{label} 重复定义 {normalized}")
            server[normalized] = value
        if set(server) - {"name", "endpoint", "type", "protocol", "api_key"}:
            raise RuntimeError(f"{label} 仅支持 name、endpoint、protocol、api_key")
        if server.get("type", "url") != "url":
            raise RuntimeError(f"{label} 仅支持远程 URL MCP")
        name = _string(server.get("name"), f"{label}.name")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) or name in names:
            raise RuntimeError(
                f"{label}.name 必须唯一且匹配 [A-Za-z][A-Za-z0-9_-]{{0,63}}"
            )
        names.add(name)
        endpoint = _string(server.get("endpoint"), f"{label}.endpoint")
        try:
            url = urlsplit(endpoint)
            valid = (
                url.scheme in {"https", "http"}
                and url.hostname
                and url.username is None
                and url.password is None
                and not url.fragment
                and not any(c.isspace() or ord(c) < 32 for c in endpoint)
            )
            url.port
        except ValueError:
            valid = False
        if not valid:
            raise RuntimeError(f"{label}.endpoint 必须是无内嵌凭据的 HTTP(S) 地址")
        protocol = server.get("protocol", "streamable-http")
        if protocol not in {"streamable-http", "sse"}:
            raise RuntimeError(f"{label}.protocol 仅支持 streamable-http 或 sse")
        definition = {"protocol": protocol, "endpoint": endpoint}
        if server.get("api_key"):
            key = _string(server["api_key"], f"{label}.api_key")
            if any(c in key for c in "\r\n"):
                raise RuntimeError(f"{label}.api_key 必须是单行字符串")
            definition["api_key"] = key
        servers.append(definition)
    return servers


def _skills(entries):
    """校验 Direct 的 Skill Hub / Skill Space 引用并序列化为 SKILLS。

    当前 Harness App 环境变量契约只接受字符串引用，不接受 ZIP 来源对象。
    不可用的对象或 URL 直接报错，避免把未支持的 Skill 格式当成已启用。
    """
    refs = []
    for index, entry in enumerate(entries):
        label = f"harness.skills[{index}]"
        if not isinstance(entry, str):
            raise RuntimeError(
                f"{label} 仅支持 Skill Hub slug 或 Skill Space 字符串引用；不支持 ZIP 对象"
            )
        ref = _string(entry, label)
        if "," in ref or "://" in ref or any(c.isspace() for c in ref):
            raise RuntimeError(f"{label} 必须是单个 Skill 引用，不能是 URL")
        if ref.startswith("ss-") and not re.fullmatch(
            r"ss-[A-Za-z0-9_-]+(?::s-[A-Za-z0-9_-]+)?", ref
        ):
            raise RuntimeError(f"{label} 的 Skill Space 引用格式无效")
        if ref not in refs:
            refs.append(ref)
    return ",".join(refs)


def configure_integrations(config, mode, *, require_model_key=False):
    """转换配置，不修改 YAML 或向工具 Worker 注入模型密钥。

    输入：已校验的资源配置及模式。读取同一个 config.yaml 的模型扩展字段。
    输出：三模式的模型配置；仅 Direct 注入 MCP 和 Skill，Queue 跳过这两项。
    冲突：能力配置必须写在 harness 下，不能同时通过 runtime_template.envs 覆盖。
    """
    direct = mode == "direct"
    raw = _read_yaml()
    model = raw["harness"]["model"]
    provider = _string(model.get("provider", "openai"), "harness.model.provider")
    if not direct and provider != "openai":
        raise RuntimeError("Queue 示例使用方舟命名 Key，只支持 openai 兼容协议")
    conflicts = sorted(MANAGED_ENVS.intersection(config.runtime_template.envs))
    if conflicts:
        raise RuntimeError(
            "请将模型、Skill、MCP 配置移到 harness，移除 runtime_template.envs 中的："
            + ", ".join(conflicts)
        )
    envs = dict(config.runtime_template.envs)
    envs.update(
        {
            "MODEL_AGENT_NAME": config.model_id,
            "MODEL_AGENT_PROVIDER": provider,
            "MODEL_AGENT_API_BASE": config.model_base_url,
        }
    )
    tools = list(config.harness.tools)
    if direct:
        envs.update(
            {
                "MODEL_PROVIDER": provider,
                "MCP_SERVERS": json.dumps(
                    _mcp_servers(config.harness.mcp_servers), ensure_ascii=False
                ),
                "SKILLS": _skills(config.harness.skills),
            }
        )
        key = _string(
            model.get("api_key", ""), "harness.model.api_key", allow_empty=True
        )
        if key:
            envs["MODEL_API_KEY"] = key
        elif config.model_api_key_name:
            # VeADK 使用 Runtime IAM 权限按名称取 Key，无须在 YAML 填写明文。
            envs["MODEL_AGENT_API_KEY_NAME"] = config.model_api_key_name
    else:
        # 共享 YAML 中的 Direct MCP 配置及工具绑定不进入 Queue Harness。
        tools = [
            tool
            for tool in tools
            if not isinstance(tool, dict)
            or tool.get("Type", tool.get("type")) != "mcp_toolset"
        ]
        if require_model_key and not config.model_api_key_name:
            raise RuntimeError("Queue 模式必须填写 harness.model.api_key_name")
    return replace(
        config,
        harness=replace(config.harness, tools=tools, mcp_servers=[], skills=[]),
        runtime_template=replace(config.runtime_template, envs=envs),
    )
