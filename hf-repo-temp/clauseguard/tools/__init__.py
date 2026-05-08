"""ClauseGuard tools package."""

from clauseguard.tools.clause_tools import clean_text, detect_contract_type, detect_headings, split_into_clauses
from clauseguard.tools.file_tools import detect_encoding, extract_text, read_docx, read_pdf, read_txt
from clauseguard.tools.report_tools import format_markdown, risk_color, severity_badge, severity_emoji

__all__ = [
    "clean_text",
    "detect_contract_type",
    "detect_encoding",
    "detect_headings",
    "extract_text",
    "format_markdown",
    "read_docx",
    "read_pdf",
    "read_txt",
    "risk_color",
    "severity_badge",
    "severity_emoji",
    "split_into_clauses",
]
