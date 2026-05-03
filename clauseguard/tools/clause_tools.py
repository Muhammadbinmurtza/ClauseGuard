"""Clause processing utility functions."""

import re
from typing import List


def split_into_clauses(text: str) -> List[str]:
    """Split a contract document into individual clauses.

    Splits on: numbered patterns (1., 1.1, Article 1, Section 1, etc.),
    ALL CAPS headings, and double newline breaks.

    Args:
        text: The full text of the contract document.

    Returns:
        A list of non-empty clause strings.
    """
    if not text or not text.strip():
        return []

    _paragraphs = _split_by_numbered_headings(text)
    clauses: List[str] = []

    for para in _paragraphs:
        sub_clauses = _split_by_double_newlines(para)
        clauses.extend(c for c in sub_clauses if c.strip())

    return [c for c in clauses if len(c.split()) >= 5]


def _split_by_numbered_headings(text: str) -> List[str]:
    """Split text by numbered section patterns and ALL CAPS headings."""
    pattern = r"(?:(?<=\n)\s*(?:Article|Section|SECTION|ARTICLE)\s+\d+[\.:\s]|\n\s*(?:\d+[\.\)]\s*[A-Z]|\d+\.\d+\s+[A-Z]|[IVX]+\.\s+[A-Z])|\n\s*[A-Z][A-Z\s]{10,}\n)"
    parts = re.split(pattern, text)
    return [p.strip() for p in parts if p.strip()]


def _split_by_double_newlines(text: str) -> List[str]:
    """Split text by double newline breaks."""
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def clean_text(text: str) -> str:
    """Clean and normalize text by removing excessive whitespace.

    Args:
        text: Raw text to clean.

    Returns:
        Cleaned and normalized text.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\t+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n +", "\n", text)
    return text.strip()


_CONTRACT_KEYWORDS: dict[str, List[str]] = {
    "NDA": ["non-disclosure", "confidential", "confidentiality", "trade secret", "nda", "non disclosure"],
    "Employment": ["employment", "employee", "salary", "benefits", "at-will", "at will", "offer letter"],
    "Freelance": ["freelance", "independent contractor", "consultant", "statement of work", "contractor"],
    "SaaS": ["software as a service", "subscription", "saas", "service level agreement", "sla", "license"],
}


def detect_contract_type(text: str) -> str:
    """Detect the type of contract based on keyword analysis.

    Args:
        text: The full text of the contract document.

    Returns:
        Detected contract type string (NDA, Employment, Freelance, SaaS, or Other).
    """
    if not text:
        return "Other"

    text_lower = text.lower()
    scores: dict[str, int] = {}

    for contract_type, keywords in _CONTRACT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[contract_type] = score

    if not scores:
        return "Other"

    return max(scores, key=lambda k: scores[k])


def detect_headings(text: str) -> list[str]:
    """Detect section headings from a contract document.

    Identifies ALL CAPS lines and numbered section headers.

    Args:
        text: The full text of the contract document.

    Returns:
        A list of detected heading strings.
    """
    if not text:
        return []

    headings: list[str] = []
    lines = text.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if re.match(r"^\s*(?:Article|Section|SECTION|ARTICLE)\s+\d+", stripped):
            headings.append(stripped)
            continue

        if re.match(r"^\s*\d+[\.\)]\s+[A-Z]", stripped):
            headings.append(stripped)
            continue

        if re.match(r"^[A-Z][A-Z\s]{10,}$", stripped) and len(stripped.split()) <= 6:
            headings.append(stripped)

    return headings
