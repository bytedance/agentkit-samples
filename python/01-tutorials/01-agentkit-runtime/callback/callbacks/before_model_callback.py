import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

logger = logging.getLogger(__name__)

# --- sensitive word blacklist ---
# used to intercept inappropriate requests in before_model_callback.
BLOCKED_WORDS = [
    "zanghua",
    "minganci",
    "bukexiangdeshi",
]


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    It is invoked before the agent calls the large language model (LLM).
    This callback implements two core features:
    1.  **Guardrail**：Checks if the user input contains any sensitive words from the blacklist. If so, it directly intercepts the request and does not send it to the model.
    2.  **Request Modification**：Adds a prefix to the system instruction to demonstrate how to dynamically modify the content to be sent to the model.
    """
    logger.info("--- [Model Call Before] Check and Modify Input Content ---")
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Agent '{agent_name}' is about to call the model.")

    # retrieve the latest user message text
    last_user_message = ""
    if llm_request.contents and llm_request.contents[-1].role == "user":
        if llm_request.contents[-1].parts:
            last_user_message = llm_request.contents[-1].parts[0].text or ""
    logger.info(f"[Callback] Agent '{agent_name}' 最新用户消息: '{last_user_message}'")

    # **Guardrail**：Checks if the user input contains any sensitive words from the blacklist. If so, it directly intercepts the request and does not send it to the model.
    for word in BLOCKED_WORDS:
        if word.lower() in last_user_message.lower():
            logger.warning(
                f"Detected blocked word '{word}' in user input. Request blocked."
            )
            # return a LlmResponse object to skip the actual call to the large language model
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="Sorry, the content you sent contains inappropriate words, and I cannot process it."
                        )
                    ],
                ),
                partial=True,
            )

    # **Request Modification**：Adds a prefix to the system instruction to demonstrate how to dynamically modify the content to be sent to the model.
    logger.info("Content safe, ready to add prefix to system instruction.")
    original_instruction = llm_request.config.system_instruction
    prefix = "[Modified by Callback] "

    # Extract the original instruction text
    original_text = ""
    if isinstance(original_instruction, types.Content) and original_instruction.parts:
        original_text = original_instruction.parts[0].text or ""
    elif isinstance(original_instruction, str):
        original_text = original_instruction

    # Combine the prefix with the original instruction text
    modified_text = prefix + original_text
    llm_request.config.system_instruction = modified_text
    logger.info(f"[Callback] System instruction modified to: '{modified_text}'")

    logger.info("[Callback] Continue to call the model.")
    # return None to allow the model to be called with the modified request
    return None
