# LangSmith OTel 观测方案 — 对接 AgentKit APMPlus

## 概述

本文档说明如何使用 LangChain 的 LangSmith OTel 集成，将 LangGraph Agent 的全链路 trace 数据上报到 AgentKit 平台的 APMPlus 观测后端。

对应示例代码：`langchain_otel_agent.py`

## 架构原理

```
LangGraph 节点 / LLM 调用 / 工具调用
    ↓ (LangSmith OTel 自动生成 span)
OpenTelemetry SDK (TracerProvider)
    ↓ (OTLP gRPC + x-byteapm-appkey header)
AgentKit APMPlus 后端
```

**核心思路**：利用 `langsmith.integrations.otel` 自动为所有 LangGraph 节点、LLM 调用、工具调用生成 span，再通过 OTLP exporter 将数据发送到 APMPlus，实现**零侵入式**的全链路追踪。

## 快速开始

### 1. 安装依赖

```bash
uv pip install -r requirements.txt
```

关键依赖：
- `langsmith[otel]` — LangSmith OTel 集成
- `opentelemetry-sdk` — OTel 核心
- `opentelemetry-exporter-otlp-proto-grpc` — OTLP gRPC 导出
- `opentelemetry-instrumentation-fastapi` — FastAPI HTTP 自动打点

### 2. 配置环境变量

```bash
# APMPlus 观测后端（必需）
export OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT=apmplus-cn-beijing.ivolces.com:4317
export OBSERVABILITY_OPENTELEMETRY_APMPLUS_API_KEY=your-api-key

# LLM 配置
export OPENAI_API_KEY=your-openai-key
export OPENAI_API_BASE=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
```

### 3. 运行

```bash
# 启动 HTTP 服务（监听 8000 端口）
uv run langchain_otel_agent.py

# 或本地测试（三条不同流程路径）
uv run langchain_otel_agent.py test
```

### 4. 请求示例

```bash
curl -N http://localhost:8000/invoke \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "帮我查一下订单 ORD-20240315-001 到哪了"}'
```

## 代码接入说明

只需在应用启动时添加以下初始化代码，业务逻辑**零改动**：

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# 1. 配置 Resource（含 APMPlus 业务标识）
resource = Resource.create({
    "service.name": "langchain-agent",
    "apmplus.business_carrier": "agentkit_runtime",
})

# 2. 配置 OTLP exporter（gRPC，带鉴权 header）
# 注意：gRPC metadata key 必须全小写
exporter_headers = {"x-byteapm-appkey": os.getenv("OBSERVABILITY_OPENTELEMETRY_APMPLUS_API_KEY")}

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(
        endpoint=os.getenv("OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT"),
        insecure=True,
        headers=exporter_headers,
    ))
)
trace.set_tracer_provider(tracer_provider)

# 3. LangSmith OTel 自动追踪（挂到已有 TracerProvider）
from langsmith.integrations.otel import OtelSpanProcessor
tracer_provider.add_span_processor(OtelSpanProcessor())
```

## 观测效果

在 APMPlus 后端可以看到：

| Span 类型 | 说明 |
|-----------|------|
| HTTP span | FastAPI 自动注入的请求级 trace |
| agent.invoke | 每次请求的顶层 span（含 user_id、session_id、prompt） |
| LangGraph 节点 | classify → research → tools → synthesize 等节点自动追踪 |
| LLM 调用 | 每次 ChatOpenAI 调用的 input/output/tokens/latency |
| 工具调用 | 每次 tool 调用的参数和返回值 |

Resource attributes 包含 `apmplus.business_carrier=agentkit_runtime`，便于在平台侧按业务载体筛选。

## Agent 多步骤流程

示例 Agent 使用 LangGraph 构建了多步骤工作流：

```
START → classify → route
                     ├── simple_qa → END          (知识库直答)
                     ├── research ⇄ tools → synthesize → END  (工具调用+综合)
                     └── escalation → END         (升级工单)
```

三个测试 prompt 分别触发不同路径：

1. `"你们的退款政策是什么？"` → classify → simple_qa → END
2. `"帮我查一下订单 ORD-20240315-001 到哪了"` → classify → research → tools → synthesize → END
3. `"我已经投诉三次了...我要求退款并赔偿！"` → classify → escalation → END
