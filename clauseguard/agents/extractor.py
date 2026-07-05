"""Agent 1: Extractor — segments document into individual clauses."""

import json
import logging
import re
from typing import List, Optional

from clauseguard.config.prompts import EXTRACTOR_SYSTEM_PROMPT
from clauseguard.config.settings import MAX_TOKENS, TIMEOUT_SECONDS
from clauseguard.models.clause import Clause, ClauseList
from clauseguard.services.model_service import call_model, clean_json_response

logger = logging.getLogger(__name__)

MIN_CLAUSES = 3
MAX_RETRIES = 1
EXTRACTOR_MAX_TOKENS = MAX_TOKENS
CHUNK_SIZE_WORDS = 400
CHUNK_OVERLAP_WORDS = 50


async def run_extractor(raw_text: str, filename: str = "document") -> ClauseList:
    """Extract clauses from raw contract text using programmatic splitting + LLM fallback.

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

    clauses = _programmatic_split(raw_text)
    if clauses and len(clauses) >= MIN_CLAUSES:
        logger.info("Programmatic split produced %d clauses", len(clauses))
        return ClauseList(
            clauses=clauses,
            contract_type="Other",
            total_clauses=len(clauses),
        )

    logger.info("Programmatic split yielded %d clauses (< %d), falling back to LLM", len(clauses), MIN_CLAUSES)

    word_count = len(raw_text.split())
    if word_count <= CHUNK_SIZE_WORDS:
        return await _llm_extract(raw_text, filename)

    return await _chunked_extract(raw_text, filename)


def _programmatic_split(raw_text: str) -> List[Clause]:
    """Split contract text into clauses using regex patterns — no LLM needed.

    Handles: numbered sections (1., 1.1, Article I), ALL CAPS headings,
    and paragraph breaks as fallback separators.
    """
    text = raw_text.strip()
    if not text:
        return []

    pattern = r'(?:^|\n)\s*(?:(?:\d+[\.\)]\s*)|(?:Article\s+\w+)|(?:Section\s+\d+))'
    parts = re.split(pattern, text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) < MIN_CLAUSES:
        cap_pattern = r'\n(?=[A-Z][A-Z\s]{4,}(?:\n|$))'
        parts = re.split(cap_pattern, text)
        parts = [p.strip() for p in parts if p.strip()]

    if len(parts) < MIN_CLAUSES:
        parts = [p.strip() for p in text.split('\n\n') if p.strip()]

    if len(parts) < MIN_CLAUSES:
        parts = [p.strip() for p in text.split('\n') if len(p.strip().split()) >= 5]

    if len(parts) < MIN_CLAUSES:
        return []

    clauses: List[Clause] = []
    for i, part in enumerate(parts, 1):
        heading = _extract_heading(part)
        clauses.append(Clause(
            id=i,
            raw_text=part,
            plain_english=None,
            clause_type="OTHER",
            section_heading=heading,
            position=i,
        ))

    return clauses


def _extract_heading(text: str) -> Optional[str]:
    """Extract a section heading from the start of a clause."""
    text = text.strip()
    heading_match = re.match(r'^([A-Z][A-Z\s]{3,50})(?:\.|\n|$)', text)
    if heading_match:
        return heading_match.group(1).strip()
    numbered = re.match(r'^(\d+[\.\)]\s*.+?)(?:\.|\n|$)', text)
    if numbered and len(numbered.group(1)) <= 60:
        return numbered.group(1).strip()
    return None


async def _llm_extract(raw_text: str, filename: str) -> ClauseList:
    """Use the LLM to extract clauses (fallback for documents without clear structure)."""
    prompt = _build_user_prompt(raw_text, filename)

    content = await call_model(
        system_prompt=EXTRACTOR_SYSTEM_PROMPT,
        user_prompt=prompt,
        agent_name="Extractor",
        max_retries=MAX_RETRIES,
        max_tokens=EXTRACTOR_MAX_TOKENS,
        timeout=TIMEOUT_SECONDS,
    )

    if content is None:
        raise ValueError("Extractor agent failed to produce a valid response")

    clause_list = _parse_response(content)
    _validate_clause_list(clause_list)
    _warn_potential_truncation(clause_list, raw_text)
    return clause_list


async def _chunked_extract(raw_text: str, filename: str) -> ClauseList:
    """Split a large document into chunks, extract from each, then merge."""
    words = raw_text.split()
    chunks: List[str] = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + CHUNK_SIZE_WORDS])
        chunks.append(chunk)
        i += CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS

    logger.info("Chunking %d-word document into %d chunks", len(words), len(chunks))

    all_clauses: List[Clause] = []
    for idx, chunk in enumerate(chunks):
        try:
            chunk_result = await _llm_extract(chunk, f"{filename}_chunk_{idx+1}")
            for clause in chunk_result.clauses:
                clause.id = len(all_clauses) + 1
                clause.position = len(all_clauses) + 1
                all_clauses.append(clause)
        except ValueError:
            logger.warning("Chunk %d extraction failed, skipping", idx + 1)

    if len(all_clauses) < MIN_CLAUSES:
        raise ValueError(
            f"Document too short or unreadable — minimum {MIN_CLAUSES} clauses required"
        )

    logger.info("Chunked extraction produced %d total clauses", len(all_clauses))
    return ClauseList(
        clauses=all_clauses,
        contract_type="Other",
        total_clauses=len(all_clauses),
    )


def _build_user_prompt(raw_text: str, filename: str) -> str:
    """Build the user prompt with the contract text."""
    return f"""Extract all clauses from the following contract document.

Filename: {filename}

Document text:
{raw_text}
"""


def _parse_response(content: str) -> ClauseList:
    """Parse the LLM JSON response into a ClauseList."""
    cleaned = clean_json_response(content)
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


def _validate_clause_list(clause_list: ClauseList) -> None:
    """Validate the extracted clause list meets minimum requirements.

    Raises:
        ValueError: If fewer than MIN_CLAUSES clauses are found.
    """
    if clause_list.total_clauses < MIN_CLAUSES:
        raise ValueError(
            f"Document too short or unreadable — minimum {MIN_CLAUSES} clauses required"
        )


def _warn_potential_truncation(clause_list: ClauseList, raw_text: str) -> None:
    """Log a warning if the clause count seems too low for the document size."""
    word_count = len(raw_text.split())
    cl = clause_list.total_clauses
    if cl > 0:
        words_per_clause = word_count / cl
        if cl <= 5 and word_count > 500:
            logger.warning(
                "Possible token truncation: only %d clauses extracted from %d-word document "
                "(avg %.0f words/clause — expected ~30-80). "
                "The LLM response may have been cut off before all clauses were output. "
                "Try increasing MAX_TOKENS in settings.",
                cl, word_count, words_per_clause,
            )
