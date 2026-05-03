"""Agent 1: Extractor — segments document into individual clauses."""

import asyncio
import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from clauseguard.config.prompts import EXTRACTOR_SYSTEM_PROMPT
from clauseguard.config.settings import BASE_URL, DEEPSEEK_API_KEY, MAX_TOKENS, MODEL_NAME, TEMPERATURE, TIMEOUT_SECONDS
from clauseguard.models.clause import Clause, ClauseList

logger = logging.getLogger(__name__)

MIN_CLAUSES = 3
MAX_CLAUSES_VAL = 60
MAX_RETRIES = 1


async def run_extractor(raw_text: str, filename: str = "document") -> ClauseList:
    """Extract clauses from raw contract text using the Extractor agent.

    Args:
        raw_text: The raw text content of the contract.
        filename: Name of the source file (for context).

    Returns:
        A ClauseList containing the extracted clauses.

    Raises:
        ValueError: If fewer than MIN_CLAUSES clauses are found.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Document is empty or unreadable")

    client = _build_client()
    prompt = _build_user_prompt(raw_text, filename)

    content = await _call_with_retry(
        client,
        system_prompt=EXTRACTOR_SYSTEM_PROMPT,
        user_prompt=prompt,
        agent_name="Extractor",
    )

    clause_list = _parse_response(content)
    _validate_clause_list(clause_list)
    return clause_list


async def _call_with_retry(
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    agent_name: str,
) -> str | None:
    """Call the LLM with retry on JSON parse failure and timeout enforcement."""
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                ),
                timeout=TIMEOUT_SECONDS,
            )
            content = response.choices[0].message.content or ""
            json.loads(_clean_json_response(content))
            return content
        except json.JSONDecodeError as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                logger.warning("%s returned malformed JSON, retrying...", agent_name)
                user_prompt += "\n\nIMPORTANT: Output ONLY raw JSON."
        except asyncio.TimeoutError:
            logger.error("%s agent timed out after %ds", agent_name, TIMEOUT_SECONDS)
            return None
        except Exception as e:
            logger.error("%s agent failed: %s", agent_name, e)
            return None
    logger.error("%s failed to produce valid JSON: %s", agent_name, last_error)
    return None


def _build_client() -> AsyncOpenAI:
    """Build an AsyncOpenAI client configured for DeepSeek."""
    return AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=BASE_URL)


def _build_user_prompt(raw_text: str, filename: str) -> str:
    """Build the user prompt with the contract text."""
    return f"""Extract all clauses from the following contract document.

Filename: {filename}

Document text:
{raw_text}
"""


def _parse_response(content: str) -> ClauseList:
    """Parse the LLM JSON response into a ClauseList.

    Args:
        content: The raw response string from the LLM.

    Returns:
        A ClauseList parsed from the JSON response.
    """
    cleaned = _clean_json_response(content)
    data = json.loads(cleaned)

    if isinstance(data, list):
        clauses_data = data
    elif isinstance(data, dict):
        clauses_data = data.get("clauses", [])
    else:
        clauses_data = []

    clauses: list[Clause] = []
    for c in clauses_data:
        clauses.append(
            Clause(
                id=c.get("id", 0),
                raw_text=c.get("raw_text", ""),
                plain_english=c.get("plain_english"),
                clause_type=c.get("clause_type", "OTHER"),
                section_heading=c.get("section_heading"),
                position=c.get("position", 0),
            )
        )

    contract_type_raw = data.get("contract_type", "Other") if isinstance(data, dict) else "Other"

    return ClauseList(
        clauses=clauses,
        contract_type=contract_type_raw,
        total_clauses=len(clauses),
    )


def _clean_json_response(content: str) -> str:
    """Strip markdown fences and leading/trailing text from LLM JSON output."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    return content


def _validate_clause_list(clause_list: ClauseList) -> None:
    """Validate the extracted clause list meets minimum requirements.

    Raises:
        ValueError: If fewer than MIN_CLAUSES clauses are found.
    """
    if clause_list.total_clauses < MIN_CLAUSES:
        raise ValueError(
            f"Document too short or unreadable — minimum {MIN_CLAUSES} clauses required"
        )
