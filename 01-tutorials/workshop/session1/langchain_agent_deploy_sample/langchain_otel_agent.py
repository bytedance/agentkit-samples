import os
import json
import logging
from typing import TypedDict, Annotated, Literal
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

# OpenTelemetry — 最少侵入式接入
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============ 0. OpenTelemetry 初始化（仅需这几行） ============
OTEL_ENDPOINT = os.getenv("OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT", "http://localhost:4317")
OTEL_API_KEY = os.getenv("OBSERVABILITY_OPENTELEMETRY_APMPLUS_API_KEY", "")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "langchain-agent")

resource = Resource.create({
    "service.name": SERVICE_NAME,
    "apmplus.business_carrier": "agentkit_runtime",
})

# 配置 OTLP exporter，header 中带上 ByteAPM AppKey
# 注意：gRPC metadata key 必须全小写
exporter_headers = {}
if OTEL_API_KEY:
    exporter_headers["x-byteapm-appkey"] = OTEL_API_KEY

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(
        endpoint=OTEL_ENDPOINT,
        insecure=True,
        headers=exporter_headers,
    ))
)
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# LangSmith OTel 自动追踪（自动为所有 LangChain/LangGraph 调用生成 span）
# 无需手动在每个节点加 tracer，LangGraph 的每个节点、LLM 调用、工具调用都会自动生成子 span
try:
    from langsmith.integrations.otel import configure as configure_langsmith_otel
    configure_langsmith_otel(
        project_name=os.getenv("LANGSMITH_PROJECT", SERVICE_NAME),
    )
    logger.info("LangSmith OTel auto-tracing enabled")
except ImportError:
    logger.warning("langsmith not installed, skipping auto-tracing. pip install langsmith")
except Exception as e:
    logger.warning(f"LangSmith OTel configure failed: {e}, falling back to manual tracing only")


# ============ 1. 定义状态 ============
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    classification: str
    final_answer: str


# ============ 2. 定义工具 ============
@tool
def search_knowledge_base(query: str) -> str:
    """搜索内部知识库获取相关信息"""
    knowledge = {
        "退款": "退款政策：7天无理由退款，需提供订单号。处理时间3-5个工作日。",
        "配送": "标准配送3-5天，加急配送1-2天。满99元免运费。",
        "账户": "账户问题请提供注册邮箱，支持修改密码、更换手机号、注销账户。",
    }
    for key, value in knowledge.items():
        if key in query:
            return value
    return "未找到相关信息，建议转人工客服。"


@tool
def check_order_status(order_id: str) -> str:
    """查询订单状态"""
    return f"订单 {order_id} 状态：已发货，预计明天送达。快递单号: SF1234567890"


@tool
def create_ticket(summary: str, priority: str) -> str:
    """创建工单，用于需要人工跟进的问题"""
    return f"工单已创建 - 摘要: {summary}, 优先级: {priority}, 工单号: TK-2024-001"


# ============ 3. LLM 和工具绑定 ============
llm = ChatOpenAI(
    model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
    temperature=0,
)

tools = [search_knowledge_base, check_order_status, create_ticket]
llm_with_tools = llm.bind_tools(tools)


# ============ 4. 定义各节点（无需手动加 span，LangSmith OTel 自动追踪） ============
def classify_intent(state: AgentState) -> AgentState:
    """意图分类节点"""
    messages = state["messages"]
    response = llm.invoke([
        SystemMessage(content="""对用户问题进行分类，只返回以下类别之一：
        - simple_qa: 简单问答，知识库可直接回答
        - order_query: 订单查询相关
        - complex_issue: 复杂问题，需要人工介入
        回复格式：只返回类别名称"""),
        messages[-1]
    ])
    return {"classification": response.content.strip()}


def simple_qa_node(state: AgentState) -> AgentState:
    """简单问答：查知识库直接回答"""
    user_msg = state["messages"][-1].content
    result = search_knowledge_base.invoke({"query": user_msg})
    response = llm.invoke([
        SystemMessage(content="基于以下知识库信息，友好地回答用户问题。"),
        HumanMessage(content=f"知识库信息：{result}\n\n用户问题：{user_msg}")
    ])
    return {"messages": [response], "final_answer": response.content}


def research_node(state: AgentState) -> AgentState:
    """调研节点：调用工具收集信息"""
    response = llm_with_tools.invoke([
        SystemMessage(content="你是客服助手，使用工具收集解决问题所需的信息。"),
        *state["messages"]
    ])
    return {"messages": [response]}


tool_node = ToolNode(tools)


def synthesize_node(state: AgentState) -> AgentState:
    """综合节点：整合所有信息生成最终回答"""
    response = llm.invoke([
        SystemMessage(content="""基于收集到的所有信息，生成最终回答。要求：
        1. 清晰总结问题处理结果
        2. 如有后续步骤，明确告知用户
        3. 语气友好专业"""),
        *state["messages"]
    ])
    return {"messages": [response], "final_answer": response.content}


def escalation_node(state: AgentState) -> AgentState:
    """升级节点：创建工单转人工"""
    user_msg = state["messages"][0].content
    ticket_result = create_ticket.invoke({
        "summary": user_msg[:100],
        "priority": "high"
    })
    response = llm.invoke([
        SystemMessage(content="告知用户问题已升级，提供工单信息，安抚用户。"),
        HumanMessage(content=f"工单创建结果：{ticket_result}")
    ])
    return {"messages": [response], "final_answer": response.content}


# ============ 5. 路由逻辑 ============
def route_by_classification(state: AgentState) -> Literal["simple_qa", "research", "escalation"]:
    classification = state.get("classification", "")
    if "simple_qa" in classification:
        return "simple_qa"
    elif "order_query" in classification:
        return "research"
    else:
        return "escalation"


def should_continue_tools(state: AgentState) -> Literal["tools", "synthesize"]:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return "synthesize"


# ============ 6. 构建图 ============
# 流程：
#   START → classify → route
#                        ├── simple_qa → END
#                        ├── research ⇄ tools → synthesize → END
#                        └── escalation → END

workflow = StateGraph(AgentState)

workflow.add_node("classify", classify_intent)
workflow.add_node("simple_qa", simple_qa_node)
workflow.add_node("research", research_node)
workflow.add_node("tools", tool_node)
workflow.add_node("synthesize", synthesize_node)
workflow.add_node("escalation", escalation_node)

workflow.add_edge(START, "classify")
workflow.add_conditional_edges("classify", route_by_classification)
workflow.add_edge("simple_qa", END)
workflow.add_conditional_edges("research", should_continue_tools)
workflow.add_edge("tools", "research")
workflow.add_edge("synthesize", END)
workflow.add_edge("escalation", END)

agent = workflow.compile()


# ============ 7. FastAPI 服务 ============
app = FastAPI(title="LangGraph Agent Service")

# 自动为 FastAPI HTTP 请求添加 tracing
FastAPIInstrumentor.instrument_app(app)


@app.post("/invoke")
async def invoke(request: Request):
    """
    POST /invoke
    Body: {"prompt": "你的问题", "user_id": "xxx", "session_id": "xxx"}
    返回: ndjson 流式响应，符合 ADK event 规范
    """
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        return {"error": "prompt is required"}

    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id", "default_session")
    logger.info(f"user={user_id}, session={session_id}, prompt={prompt}")

    async def event_stream():
        # 只需一个顶层 span 标记请求入口，内部节点/LLM/工具的 span 由 LangSmith OTel 自动生成
        with tracer.start_as_current_span("agent.invoke") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_id", session_id)
            span.set_attribute("prompt", prompt[:200])

            inputs = {"messages": [HumanMessage(content=prompt)]}
            try:
                async for chunk in agent.astream(inputs, stream_mode="updates"):
                    for node, state in chunk.items():
                        logger.info(f"执行节点: {node}")
                        if "messages" in state and state["messages"]:
                            last_msg = state["messages"][-1]
                            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                            if content:
                                event_data = {
                                    "content": {
                                        "parts": [{"text": content}]
                                    }
                                }
                                yield json.dumps(event_data) + "\n"
            except Exception as e:
                logger.error(f"Agent error: {e}")
                span.set_status(trace.StatusCode.ERROR, str(e))
                span.record_exception(e)
                event_data = {"content": {"parts": [{"text": f"处理出错: {str(e)}"}]}}
                yield json.dumps(event_data) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ============ 8. 本地测试 ============
# 三个 prompt 触发三条不同路径
async def local_test():
    test_cases = [
        {
            # 流程 1: classify → simple_qa → END
            "prompt": "你们的退款政策是什么？",
            "expected_flow": "classify → simple_qa → END",
        },
        {
            # 流程 2: classify → research → tools → research → synthesize → END
            "prompt": "帮我查一下订单 ORD-20240315-001 到哪了",
            "expected_flow": "classify → research ⇄ tools → synthesize → END",
        },
        {
            # 流程 3: classify → escalation → END
            "prompt": "我已经投诉三次了，每次都说处理中但一直没结果，我要求退款并赔偿！",
            "expected_flow": "classify → escalation → END",
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {case['prompt']}")
        print(f"预期流程: {case['expected_flow']}")
        print(f"{'='*60}")

        inputs = {"messages": [HumanMessage(content=case["prompt"])]}
        nodes_visited = []
        async for chunk in agent.astream(inputs, stream_mode="updates"):
            for node, state in chunk.items():
                nodes_visited.append(node)
                if "messages" in state and state["messages"]:
                    last_msg = state["messages"][-1]
                    content = last_msg.content if hasattr(last_msg, "content") else ""
                    if content:
                        print(f"  [{node}] {content[:120]}")

        print(f"  实际经过节点: {' → '.join(nodes_visited)}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # python langchain_otel_agent.py test
        import asyncio
        asyncio.run(local_test())
    else:
        # python langchain_otel_agent.py
        uvicorn.run(app, host="0.0.0.0", port=8000)
