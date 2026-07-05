"""Model service layer — unified Qwen/vLLM inference via OpenAI-compatible API.

Provides a single shared client and reusable inference functions for all
ClauseGuard agents and the copilot. Handles retries, timeouts, JSON cleaning,
and graceful error recovery.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI, OpenAI

from clauseguard.config.settings import (
    API_KEY,
    BASE_URL,
    MAX_TOKENS,
    MODEL_NAME,
    TEMPERATURE,
    TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

_async_client: AsyncOpenAI | None = None
_sync_client: OpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Return the shared AsyncOpenAI client (lazy singleton)."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    return _async_client


def get_sync_client() -> OpenAI:
    """Return the shared synchronous OpenAI client (lazy singleton)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    return _sync_client


def reset_client() -> None:
    """Reset the shared clients — useful for testing or config changes."""
    global _async_client, _sync_client
    _async_client = None
    _sync_client = None


def clean_json_response(content: str) -> str:
    """Strip markdown fences and leading/trailing non-JSON text from LLM output."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def repair_json(content: str) -> str | None:
    """Attempt to repair common JSON formatting issues from smaller LLMs.

    Tries increasingly aggressive fixes and returns the repaired string,
    or None if the content cannot be salvaged.
    """
    original = content.strip()
    attempts: list[str] = [original]

    if "{" in content:
        start = content.index("{")
        end = content.rindex("}")
        clipped = content[start:end + 1]
        if clipped != original:
            attempts.append(clipped)
    if "[" in content:
        start = content.index("[")
        end = content.rindex("]")
        clipped = content[start:end + 1]
        if clipped not in attempts:
            attempts.append(clipped)

    for prefix in ('{"clauses"', '{"contract"', '{"clause"'):
        for attempt in attempts:
            if attempt.endswith(prefix[:-1]):
                fixed = attempt + ']}'
                if fixed not in attempts:
                    attempts.append(fixed)
            if attempt.rstrip(",").endswith(prefix[:-1]):
                fixed = attempt.rstrip(",") + ']}'
                if fixed not in attempts:
                    attempts.append(fixed)

    for attempt in attempts:
        try:
            json.loads(attempt)
            return attempt
        except json.JSONDecodeError:
            continue

    for attempt in attempts:
        try:
            repaired = attempt.rstrip(",\n\r\t ") + "]}"
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            continue

    for attempt in attempts:
        try:
            repaired = "{" + attempt.strip().lstrip("{") + "]}"
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            continue

    return None


async def call_model(
    system_prompt: str,
    user_prompt: str,
    *,
    agent_name: str = "Agent",
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int | None = None,
    max_retries: int = 1,
    validate_json: bool = True,
) -> str | None:
    """Call the Qwen model with retry, timeout, and JSON validation.

    Args:
        system_prompt: The system-level instruction.
        user_prompt: The user-level query.
        agent_name: Label used in log messages.
        temperature: Sampling temperature (defaults to config TEMPERATURE).
        max_tokens: Max tokens for the response (defaults to config MAX_TOKENS).
        timeout: Per-call timeout in seconds (defaults to config TIMEOUT_SECONDS).
        max_retries: Number of additional retries on JSON parse failure.
        validate_json: Whether to validate the response as valid JSON.

    Returns:
        The model's raw text response, or None if all attempts fail.
    """
    client = get_client()
    temp = temperature if temperature is not None else TEMPERATURE
    mt = max_tokens if max_tokens is not None else MAX_TOKENS
    tout = timeout if timeout is not None else TIMEOUT_SECONDS

    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                    max_tokens=mt,
                ),
                timeout=tout,
            )
            content = response.choices[0].message.content or ""
            logger.info("%s received %d chars in %d attempt(s)", agent_name, len(content), attempt + 1)

            if validate_json:
                cleaned = clean_json_response(content)
                if not cleaned or not cleaned.strip():
                    raise ValueError("Empty response")
                json.loads(cleaned)
                logger.info("%s produced valid JSON", agent_name)
            return content

        except json.JSONDecodeError as e:
            last_error = str(e)
            preview = content[:200] if 'content' in dir() else "(no content)"
            logger.warning("%s returned malformed JSON (attempt %d): %s | preview: %s", agent_name, attempt + 1, e, preview)
            if 'content' in dir():
                repaired = repair_json(content)
                if repaired:
                    logger.info("%s JSON was repaired automatically", agent_name)
                    return repaired
            if attempt < max_retries:
                logger.warning("%s returned malformed JSON, retrying...", agent_name)
                user_prompt += "\n\nIMPORTANT: Output ONLY raw JSON. No markdown, no explanation."
        except ValueError as e:
            last_error = str(e)
            if attempt < max_retries:
                logger.warning("%s returned empty response, retrying...", agent_name)
        except asyncio.TimeoutError:
            logger.error("%s agent timed out after %ds", agent_name, tout)
            return None
        except Exception as e:
            logger.error("%s agent failed: %s", agent_name, e)
            return None

    logger.error("%s failed to produce valid JSON: %s", agent_name, last_error)
    return None


async def call_model_chat(
    messages: List[Dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int = 60,
) -> str:
    """Call the Qwen model for chat (multi-turn conversation).

    Args:
        messages: Full message list (system + history + user).
        temperature: Sampling temperature.
        max_tokens: Max tokens for the response.
        timeout: Per-call timeout in seconds.

    Returns:
        The assistant's text response, or a friendly error message.
    """
    client = get_client()
    temp = temperature if temperature is not None else TEMPERATURE
    mt = max_tokens if max_tokens is not None else MAX_TOKENS

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=temp,
                max_tokens=mt,
            ),
            timeout=timeout,
        )
        content = response.choices[0].message.content
        return content or "I'm sorry, I couldn't generate a response. Please try again."
    except asyncio.TimeoutError:
        logger.error("Chat call timed out after %ds", timeout)
        return "I'm sorry, the request timed out. Please try a shorter question or try again."
    except Exception as e:
        logger.error("Chat call failed: %s", e)
        return f"I'm sorry, something went wrong: {e}"


# ── Synchronous wrappers for use in Streamlit callbacks ──


def call_model_chat_sync(
    messages: List[Dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int = 60,
) -> str:
    """Synchronous wrapper around call_model_chat for Streamlit callbacks."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                call_model_chat(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
            )
        finally:
            loop.close()
        return result
    except Exception as e:
        logger.error("call_model_chat_sync failed: %s", e)
        return f"Sorry, an unexpected error occurred: {e}"


# ── Higher-level domain functions ──


async def analyze_clause(
    clause_text: str,
    clause_type: str = "",
    additional_context: str = "",
    system_prompt: str = "",
    user_prompt_template: str = "",
    agent_name: str = "Analyzer",
) -> str | None:
    """Analyze a single clause — used by pipeline agents.

    Args:
        clause_text: The clause raw text to analyze.
        clause_type: Optional pre-classified clause type.
        additional_context: Additional context to append.
        system_prompt: The agent-specific system prompt.
        user_prompt_template: A template string for the user prompt.
        agent_name: Label for logging.

    Returns:
        Raw response string or None.
    """
    user_prompt = user_prompt_template.format(
        clause_text=clause_text,
        clause_type=clause_type,
        context=additional_context,
    ) if user_prompt_template else clause_text

    return await call_model(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        agent_name=agent_name,
    )


async def generate_negotiation_message(
    clause_text: str,
    risk_reason: str,
    safer_version: str = "",
) -> str:
    """Generate a professional negotiation message for a risky clause."""
    system = (
        "You are a professional contract negotiator. Write a short, polite email "
        "message requesting a change to a contract clause. Keep it professional, "
        "concise, and non-confrontational. Maximum 4-5 sentences."
    )
    user = (
        f"The risky clause is:\n\"{clause_text}\"\n\n"
        f"Why it's risky:\n{risk_reason}\n\n"
    )
    if safer_version:
        user += f"Suggested safer version:\n\"{safer_version}\"\n\n"
    user += "Write a single email-style negotiation message requesting a fair revision."

    result = await call_model(
        system_prompt=system,
        user_prompt=user,
        agent_name="NegotiationGenerator",
        validate_json=False,
    )
    return result or ""


async def contract_chat(
    contract_context: str,
    chat_history: List[Dict[str, str]],
    user_message: str,
    system_prompt: str,
    timeout: int = 60,
) -> str:
    """Handle a contract chat conversation with full contract context.

    Args:
        contract_context: The formatted contract + analysis context.
        chat_history: Previous messages (role/content dicts).
        user_message: The user's new question.
        system_prompt: The copilot system prompt.
        timeout: Per-call timeout.

    Returns:
        Assistant response string.
    """
    full_system = f"{system_prompt}\n\n---\n\n## CONTRACT CONTEXT\n\n{contract_context}"

    messages: List[Dict[str, str]] = [{"role": "system", "content": full_system}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    return await call_model_chat(messages, timeout=timeout)
