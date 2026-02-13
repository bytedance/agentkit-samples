"""
Video Breakdown Agent — AgentKit 部署入口

Agent 定义位于 video_breakdown_agent/agent.py（veadk web 的唯一真相来源）。
本文件仅添加 Runner、可观测性、AgentkitAgentServerApp 等部署层。

运行方式：
  1. uv run veadk web        — 本地开发（veadk web 自动发现 video_breakdown_agent/）
  2. python agent.py          — AgentKit 部署
"""

import logging
import os

from veadk import Runner
from veadk.memory.short_term_memory import ShortTermMemory
from agentkit.apps import AgentkitAgentServerApp

# 从包中导入唯一的 root_agent 定义
from video_breakdown_agent.agent import root_agent

# ==================== 日志配置 ====================

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)

# ==================== 短期记忆配置 ====================

app_name = "video_breakdown_agent"
short_term_memory = ShortTermMemory(backend="local")

# ==================== Runner (支持 veadk web / smoke_test) ====================

runner = Runner(
    agent=root_agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
)

# ==================== 可观测性（Observability） ====================
# 通过环境变量启用 OpenTelemetry Tracer：
#   VEADK_TRACER_APMPLUS=true   — APMPlus
#   VEADK_TRACER_COZELOOP=true  — CozeLoop
#   VEADK_TRACER_TLS=true       — TLS


def _load_tracer() -> None:
    """加载可观测性 Tracer（仅在对应环境变量为 true 时激活）"""
    try:
        from veadk.tracing.telemetry.exporters.apmplus_exporter import APMPlusExporter
        from veadk.tracing.telemetry.exporters.cozeloop_exporter import CozeloopExporter
        from veadk.tracing.telemetry.exporters.tls_exporter import TLSExporter
        from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer
    except ImportError:
        logger.debug("Tracing 依赖未安装，跳过可观测性初始化")
        return

    EXPORTER_REGISTRY = {
        "VEADK_TRACER_APMPLUS": APMPlusExporter,
        "VEADK_TRACER_COZELOOP": CozeloopExporter,
        "VEADK_TRACER_TLS": TLSExporter,
    }

    exporters = []
    for env_var, exporter_cls in EXPORTER_REGISTRY.items():
        if os.getenv(env_var, "").lower() == "true":
            exporters.append(exporter_cls())
            logger.info(f"可观测性: 启用 {exporter_cls.__name__}")

    if exporters:
        tracer = OpentelemetryTracer(name="veadk_tracer", exporters=exporters)
        root_agent.tracers = list(root_agent.tracers or []) + [tracer]
        logger.info(f"可观测性: 已加载 {len(exporters)} 个 Exporter")


_load_tracer()

# ==================== Server App (支持 AgentKit 部署) ====================

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
