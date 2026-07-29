import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool


SYSTEM_PROMPT = (
    "你是电商客服助手。需要查询商品或退货规则时使用工具。"
    "示例商品 ID: PROD-001 是耳机，PROD-002 是智能手表。"
    "不要编造不存在的商品或政策。"
)

PRODUCTS = {
    "PROD-001": {
        "name": "Wireless Headphones",
        "category": "audio",
        "price": "$79.99",
        "warranty": "12 months",
    },
    "PROD-002": {
        "name": "Smart Watch",
        "category": "electronics",
        "price": "$249.99",
        "warranty": "24 months",
    },
}

RETURN_POLICIES = {
    "audio": "30-day return window. Full refund within 15 days; replacement after 15 days.",
    "electronics": "30-day return window. Original packaging is required for non-defective returns.",
}


app = BedrockAgentCoreApp()
log = app.logger
_agent: Agent | None = None


@tool
def get_product_info(product_id: str) -> str:
    """Get mock product information by product ID, for example PROD-001 or PROD-002."""
    normalized = product_id.strip().upper()
    product = PRODUCTS.get(normalized)
    if product is None:
        return f"Unknown product ID: {product_id}."
    return (
        f"{normalized}: {product['name']}, category={product['category']}, "
        f"price={product['price']}, warranty={product['warranty']}."
    )


@tool
def get_return_policy(category: str) -> str:
    """Get mock return policy by product category, for example audio or electronics."""
    normalized = category.strip().lower()
    policy = RETURN_POLICIES.get(normalized)
    if policy is None:
        return f"No mock return policy for category: {category}."
    return f"Return policy for {normalized}: {policy}"


def _openai_base_url(api_base: str) -> str:
    base_url = api_base.strip().rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


def build_model() -> Any:
    model_name = os.environ.get("MODEL_AGENT_NAME", "").strip()
    api_key = os.environ.get("MODEL_AGENT_API_KEY", "").strip()
    if not model_name or not api_key:
        raise RuntimeError(
            "Set MODEL_AGENT_NAME and MODEL_AGENT_API_KEY before running this AgentCore sample."
        )

    from strands.models.openai import OpenAIModel

    client_args: dict[str, str] = {"api_key": api_key}
    api_base = os.environ.get("MODEL_AGENT_API_BASE", "").strip()
    if api_base:
        client_args["base_url"] = _openai_base_url(api_base)

    return OpenAIModel(
        model_id=model_name,
        stream=False,
        client_args=client_args,
        params={"temperature": float(os.environ.get("MODEL_AGENT_TEMPERATURE", "0.2"))},
    )


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(
            name="agentcore_support_assistant",
            model=build_model(),
            tools=[get_product_info, get_return_policy],
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
        )
    return _agent


def _prompt_from_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("prompt", "question", "input"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return "Please ask about product information or return policy."


def _extract_agent_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    message = getattr(response, "message", None)
    if isinstance(message, dict):
        blocks = message.get("content", [])
        return "".join(str(block.get("text", "")) for block in blocks)
    return str(response)


@app.entrypoint
def invoke(payload: Any, context: Any | None = None) -> str:
    """Bedrock AgentCore Runtime entrypoint preserved for AgentKit migration."""
    del context
    log.info("Invoking AgentCore Strands support agent")
    return _extract_agent_text(get_agent()(_prompt_from_payload(payload)))


if __name__ == "__main__":
    app.run()
