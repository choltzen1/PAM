"""Chat orchestration: message management, tool execution loop, context injection."""

import json
import logging
from typing import Any, Callable, Dict, List

from .client import get_openai_client, get_deployment_name
from .prompts import PETE_SYSTEM_PROMPT, PAM_DOMAIN_KNOWLEDGE
from .tools import PETE_TOOLS

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5        # max consecutive tool-call rounds before forcing a text reply
MAX_HISTORY_MESSAGES = 40   # keep last N user/assistant messages to manage token budget
MAX_CONTEXT_CHARS = 8000    # max chars for session context injection


def _trim_history(messages: List[Dict], max_messages: int = MAX_HISTORY_MESSAGES) -> List[Dict]:
    """Keep system prompt + last N non-system messages."""
    system = [m for m in messages if m.get('role') == 'system']
    non_system = [m for m in messages if m.get('role') != 'system']
    if len(non_system) <= max_messages:
        return system + non_system
    return system + non_system[-max_messages:]


def _build_session_context(session_data: Dict[str, Any]) -> str:
    """Format PETE session data for injection into the system prompt."""
    parts = []

    if session_data.get('eip_id'):
        parts.append(f"EIP_ID: {session_data['eip_id']}")
    if session_data.get('used_ban'):
        parts.append(f"BAN: {session_data['used_ban']}")
    if session_data.get('promo_code'):
        parts.append(f"Active Promo Code: {session_data['promo_code']}")

    if session_data.get('eligibility_summary'):
        summary = str(session_data['eligibility_summary'])[:MAX_CONTEXT_CHARS]
        parts.append(f"Eligibility Data:\n{summary}")

    if session_data.get('error_summary'):
        errors = str(session_data['error_summary'])[:2000]
        parts.append(f"Error Reasons:\n{errors}")

    if session_data.get('main_data_summary'):
        main = str(session_data['main_data_summary'])[:2000]
        parts.append(f"Account Data:\n{main}")

    return "\n\n".join(parts) if parts else "No session data loaded yet. The user can ask general promo questions or provide a promo code."


def pete_chat_completion(
    prompt: str,
    chat_history: List[Dict[str, str]],
    session_data: Dict[str, Any],
    tool_handlers: Dict[str, Callable],
) -> str:
    """Execute a PETE-mode chat completion with tool calling.

    Returns the assistant's text reply, or empty string if AI is unavailable
    (signaling the caller to use the keyword fallback).
    """
    client = get_openai_client()
    if not client:
        return ""

    context = _build_session_context(session_data)
    system_prompt = PETE_SYSTEM_PROMPT.format(session_context=context) + "\n\n" + PAM_DOMAIN_KNOWLEDGE

    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})
    messages = _trim_history(messages)

    return _run_tool_loop(client, messages, PETE_TOOLS, tool_handlers)


def _run_tool_loop(
    client,
    messages: List[Dict],
    tools: List[Dict],
    handlers: Dict[str, Callable],
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> str:
    """Core tool-call loop: send to LLM, execute tool calls, repeat until text reply."""
    deployment = get_deployment_name()

    for _round in range(max_rounds):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000,
            )
        except Exception as e:
            logger.error("[ai] Chat completion failed (round %d): %s: %s", _round, type(e).__name__, e)
            return f"AI error: {type(e).__name__}: {e}"

        choice = response.choices[0]
        message = choice.message

        # If no tool calls, return the text content
        if not message.tool_calls:
            return message.content or ""

        # Append the assistant message (with tool_calls) to the conversation
        messages.append(message.model_dump())

        # Execute each tool call
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            handler = handlers.get(fn_name)
            if handler:
                try:
                    result = handler(**fn_args)
                except Exception as e:
                    logger.error("[ai] Tool %s failed: %s", fn_name, e)
                    result = f"Error executing {fn_name}: {e}"
            else:
                result = f"Unknown tool: {fn_name}"
                logger.warning("[ai] LLM called unknown tool: %s", fn_name)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result),
            })

    # Exhausted tool rounds — force a text reply without tools
    logger.warning("[ai] Tool loop exhausted %d rounds, forcing final reply", max_rounds)
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error("[ai] Final chat completion failed: %s: %s", type(e).__name__, e)
        return f"AI error: {type(e).__name__}: {e}"
