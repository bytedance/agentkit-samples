import os
from pathlib import Path
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from dotenv import load_dotenv
from strands import Agent, tool


_ENV_FILE = Path(__file__).with_name(".env")
load_dotenv(_ENV_FILE, override=False)

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
        "shipping": "Ships in 2 business days",
        "stock": 18,
    },
    "PROD-002": {
        "name": "Smart Watch",
        "category": "electronics",
        "price": "$249.99",
        "warranty": "24 months",
        "shipping": "Ships in 3 business days",
        "stock": 7,
    },
}

RETURN_POLICIES = {
    "audio": "30-day return window. Full refund within 15 days; replacement after 15 days.",
    "electronics": "30-day return window. Original packaging is required for non-defective returns.",
}


app = BedrockAgentCoreApp()
log = app.logger
_agent: Agent | None = None


def _env(name: str) -> str:
    return os.environ[name].strip()


@tool
def get_product_info(product_id: str) -> str:
    """Get sample product information by product ID, for example PROD-001 or PROD-002."""
    normalized = product_id.strip().upper()
    product = PRODUCTS.get(normalized)
    if product is None:
        return f"Unknown product ID: {product_id}."
    return (
        f"{normalized}: {product['name']}, category={product['category']}, "
        f"price={product['price']}, warranty={product['warranty']}, "
        f"stock={product['stock']}, shipping={product['shipping']}."
    )


@tool
def get_return_policy(category: str) -> str:
    """Get sample return policy by product category, for example audio or electronics."""
    normalized = category.strip().lower()
    policy = RETURN_POLICIES.get(normalized)
    if policy is None:
        return f"No sample return policy for category: {category}."
    return f"Return policy for {normalized}: {policy}"


@tool
def check_product_stock(product_id: str) -> str:
    """Check sample inventory status for a product ID."""
    normalized = product_id.strip().upper()
    product = PRODUCTS.get(normalized)
    if product is None:
        return f"Unknown product ID: {product_id}."
    stock = int(product["stock"])
    if stock <= 0:
        status = "out of stock"
    elif stock < 10:
        status = "low stock"
    else:
        status = "in stock"
    return f"{normalized}: {product['name']} is {status}, stock={stock}."


@tool
def get_shipping_estimate(product_id: str) -> str:
    """Get sample shipping estimate for a product ID."""
    normalized = product_id.strip().upper()
    product = PRODUCTS.get(normalized)
    if product is None:
        return f"Unknown product ID: {product_id}."
    return f"{normalized}: {product['name']} {product['shipping']}."


@tool
def estimate_refund(product_id: str, days_since_purchase: int) -> str:
    """Estimate simple refund handling based on product category and purchase age."""
    normalized = product_id.strip().upper()
    product = PRODUCTS.get(normalized)
    if product is None:
        return f"Unknown product ID: {product_id}."
    days = max(days_since_purchase, 0)
    if days <= 15:
        action = "eligible for full refund"
    elif days <= 30:
        action = "eligible for return review or replacement"
    else:
        action = "outside the standard return window"
    return f"{normalized}: {product['name']} purchased {days} days ago is {action}."


SUPPORT_TOOLS = [
    get_product_info,
    get_return_policy,
    check_product_stock,
    get_shipping_estimate,
    estimate_refund,
]


def _openai_base_url(api_base: str) -> str:
    base_url = api_base.strip().rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


def create_model() -> Any:
    model_name = _env("MODEL_AGENT_NAME")
    api_key = _env("MODEL_AGENT_API_KEY")

    from strands.models.openai import OpenAIModel

    client_args: dict[str, str] = {
        "api_key": api_key,
        "base_url": _openai_base_url(_env("MODEL_AGENT_API_BASE")),
    }

    return OpenAIModel(
        model_id=model_name,
        stream=False,
        client_args=client_args,
        params={
            "temperature": float(os.environ.get("MODEL_AGENT_TEMPERATURE", "0.2")),
            "extra_body": {"thinking": {"type": "disabled"}},
        },
    )


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(
            name="agentcore_support_assistant",
            model=create_model(),
            tools=SUPPORT_TOOLS,
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
        return "".join(
            str(block.get("text", "")) if isinstance(block, dict) else str(block)
            for block in blocks
        )
    return str(response)


@app.entrypoint
def invoke(payload: Any, context: Any | None = None) -> str:
    """Bedrock AgentCore Runtime entrypoint preserved for AgentKit migration."""
    del context
    log.info("Invoking AgentCore Strands support agent")
    return _extract_agent_text(get_agent()(_prompt_from_payload(payload)))


if __name__ == "__main__":
    app.run()
