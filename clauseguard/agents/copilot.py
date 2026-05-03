"""ClauseGuard Copilot Agent — interactive AI chat assistant for contract analysis.

This agent handles multi-turn conversations where users ask questions about
their analyzed contract. It uses the full contract text and the completed
clause analysis report as context, and responds via the DeepSeek API.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI

from clauseguard.config.copilot_prompts import COPILOT_SYSTEM_PROMPT
from clauseguard.config.settings import BASE_URL, DEEPSEEK_API_KEY, MAX_TOKENS, MODEL_NAME, TEMPERATURE, TIMEOUT_SECONDS
from clauseguard.models.report import FinalReport

logger = logging.getLogger(__name__)

CHAT_TIMEOUT_SECONDS = 60


def _build_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=BASE_URL)


def build_contract_context(full_contract_text: str, report: FinalReport) -> str:
    """Build a detailed context string from the contract and its analysis.

    This context is injected into every copilot conversation so the AI can
    reference specific clauses, severity levels, and recommended fixes.

    Args:
        full_contract_text: The raw text of the original contract.
        report: The completed FinalReport from the analysis pipeline.

    Returns:
        A formatted context string for the copilot.
    """
    parts: List[str] = []
    parts.append("=" * 60)
    parts.append("FULL CONTRACT TEXT")
    parts.append("=" * 60)
    parts.append(full_contract_text)
    parts.append("")

    parts.append("=" * 60)
    parts.append("CLAUSE-BY-CLAUSE ANALYSIS")
    parts.append("=" * 60)
    parts.append(
        f"Contract Type: {report.summary.contract_type} | "
        f"Total Clauses: {report.summary.total_clauses} | "
        f"Risk Score: {report.summary.overall_score}/10"
    )
    parts.append(
        f"Critical: {report.summary.critical_count} | "
        f"High: {report.summary.high_count} | "
        f"Medium: {report.summary.medium_count} | "
        f"Low: {report.summary.low_count}"
    )
    parts.append("")

    for i, sc in enumerate(report.scored_clauses, 1):
        parts.append(f"--- Clause {i} ---")
        parts.append(f"Original Text: {sc.clause.raw_text}")
        parts.append(f"Clause Type: {sc.clause.clause_type.value}")
        if sc.clause.section_heading:
            parts.append(f"Section: {sc.clause.section_heading}")
        parts.append(f"Severity: {sc.finding.severity.value}")
        parts.append(f"Risk Title: {sc.finding.risk_title}")
        parts.append(f"Risk Reason: {sc.finding.risk_reason}")
        if sc.clause.plain_english:
            parts.append(f"Plain English: {sc.clause.plain_english}")
        if sc.finding.recommended_action:
            parts.append(f"Recommended Action: {sc.finding.recommended_action}")
        if sc.finding.safer_clause_version:
            parts.append(f"Safer Wording: {sc.finding.safer_clause_version}")
        if sc.finding.negotiation_message:
            parts.append(f"Negotiation Message: {sc.finding.negotiation_message}")
        if sc.finding.impact_scenarios:
            parts.append("Impact Scenarios:")
            for impact in sc.finding.impact_scenarios:
                parts.append(f"  - {impact}")
        parts.append("")

    if report.top_3_actions:
        parts.append("=" * 60)
        parts.append("TOP 3 RECOMMENDED ACTIONS")
        parts.append("=" * 60)
        for j, action in enumerate(report.top_3_actions, 1):
            parts.append(f"{j}. {action}")
        parts.append("")

    return "\n".join(parts)


def build_chat_messages(
    system_prompt: str,
    contract_context: str,
    chat_history: List[Dict[str, str]],
    user_message: str,
) -> List[Dict[str, str]]:
    """Build the full message list for the copilot chat API call.

    Args:
        system_prompt: The copilot system prompt.
        contract_context: The formatted contract + analysis context.
        chat_history: Previous messages in the conversation.
        user_message: The new user message to respond to.

    Returns:
        A list of message dicts ready for the OpenAI chat API.
    """
    full_system = f"{system_prompt}\n\n---\n\n## CONTRACT CONTEXT\n\n{contract_context}"

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": full_system},
    ]

    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    return messages


async def run_copilot(
    contract_context: str,
    chat_history: List[Dict[str, str]],
    user_message: str,
) -> str:
    """Send a user message to the copilot and return the assistant's response.

    Args:
        contract_context: The formatted contract + analysis context string.
        chat_history: Previous messages in the conversation (role/content dicts).
        user_message: The new question from the user.

    Returns:
        The assistant's text response, or an error message on failure.
    """
    client = _build_client()
    messages = build_chat_messages(COPILOT_SYSTEM_PROMPT, contract_context, chat_history, user_message)

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            ),
            timeout=CHAT_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        return content or "I'm sorry, I couldn't generate a response. Please try again."
    except asyncio.TimeoutError:
        logger.error("Copilot chat timed out")
        return "I'm sorry, the request timed out. Please try a shorter question or try again."
    except Exception as e:
        logger.error("Copilot chat failed: %s", e)
        return f"I'm sorry, something went wrong: {e}"


# ── Python 3.10+ compat: same function available as synchronous wrapper for Streamlit ──

def run_copilot_sync(
    contract_context: str,
    chat_history: List[Dict[str, str]],
    user_message: str,
) -> str:
    """Synchronous wrapper around run_copilot for use in Streamlit callbacks.

    Streamlit's chat input callback runs in the main thread, so we launch
    a fresh event loop to run the async copilot call.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                run_copilot(contract_context, chat_history, user_message)
            )
        finally:
            loop.close()
        return result
    except Exception as e:
        logger.error("run_copilot_sync failed: %s", e)
        return f"Sorry, an unexpected error occurred: {e}"
