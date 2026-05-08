"""Agent 5: Reporter — compiles the final risk report."""

import json
import logging
from datetime import datetime
from typing import List

from clauseguard.config.prompts import REPORTER_SYSTEM_PROMPT
from clauseguard.config.settings import MODEL_NAME, TEMPERATURE
from clauseguard.models.findings import ScoredClause, Severity
from clauseguard.models.report import FinalReport, RiskSummary
from clauseguard.services.model_service import call_model, clean_json_response

logger = logging.getLogger(__name__)
MAX_RETRIES = 1


async def run_reporter(
    scored_clauses: List[ScoredClause],
    contract_name: str,
    contract_type: str,
    partial: bool = False,
    truncation_note: str = "",
) -> FinalReport:
    """Compile all analysis into a structured FinalReport.

    Args:
        scored_clauses: All scored clauses with risk findings.
        contract_name: Name of the source contract file.
        contract_type: Detected type of the contract.
        partial: Whether this is a partial report due to agent failures.
        truncation_note: Note about document truncation if contract exceeded clause limit.

    Returns:
        A complete FinalReport with summary, actions, and markdown.
    """
    sorted_clauses = _sort_by_severity(scored_clauses)
    summary = _build_summary(sorted_clauses, contract_type)
    top_3 = _extract_top_actions(sorted_clauses)

    markdown = _build_markdown_programmatically(
        sorted_clauses, contract_name, contract_type, summary, top_3
    )

    return FinalReport(
        contract_name=contract_name,
        generated_at=datetime.now(),
        summary=summary,
        top_3_actions=top_3,
        scored_clauses=sorted_clauses,
        markdown_report=markdown,
        processed_normally=not partial,
        truncation_note=truncation_note,
    )


def _sort_by_severity(scored_clauses: List[ScoredClause]) -> List[ScoredClause]:
    """Sort scored clauses by severity (CRITICAL first)."""
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    return sorted(scored_clauses, key=lambda sc: severity_order.get(sc.finding.severity, 99))


def _build_summary(scored_clauses: List[ScoredClause], contract_type: str) -> RiskSummary:
    """Build risk summary statistics from scored clauses."""
    counts = {Severity.CRITICAL: 0, Severity.HIGH: 0, Severity.MEDIUM: 0, Severity.LOW: 0, Severity.INFO: 0}
    for sc in scored_clauses:
        counts[sc.finding.severity] = counts.get(sc.finding.severity, 0) + 1

    total = len(scored_clauses)
    if total > 0:
        raw_score = (
            counts[Severity.CRITICAL] * 10
            + counts[Severity.HIGH] * 7
            + counts[Severity.MEDIUM] * 4
            + counts[Severity.LOW] * 1
        ) / total
        overall_score = round(min(raw_score, 10.0), 1)
    else:
        overall_score = 0.0

    return RiskSummary(
        total_clauses=total,
        critical_count=counts[Severity.CRITICAL],
        high_count=counts[Severity.HIGH],
        medium_count=counts[Severity.MEDIUM],
        low_count=counts[Severity.LOW],
        overall_score=overall_score,
        contract_type=contract_type,
    )


def _extract_top_actions(scored_clauses: List[ScoredClause]) -> List[str]:
    """Extract the top 3 most impactful recommended actions."""
    actions: List[str] = []
    severity_priority = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]

    for sev in severity_priority:
        for sc in scored_clauses:
            if sc.finding.severity == sev and sc.finding.recommended_action:
                if sc.finding.recommended_action not in actions:
                    actions.append(sc.finding.recommended_action)
                if len(actions) >= 3:
                    return actions

    if not actions:
        actions.append("Review all clauses with legal counsel before signing.")

    return actions[:3]


def _build_markdown_programmatically(
    scored_clauses: List[ScoredClause],
    contract_name: str,
    contract_type: str,
    summary: RiskSummary,
    top_3: List[str],
) -> str:
    """Build the markdown report programmatically."""
    generated_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = [
        "# ClauseGuard Risk Report",
        f"**Contract:** {contract_name}",
        f"**Type:** {contract_type}",
        f"**Overall Risk Score:** {summary.overall_score}/10",
        f"**Generated:** {generated_str}",
        "",
        "---",
        "",
        "## Executive Summary",
        _build_executive_summary_text(scored_clauses, summary),
        "",
        "## Top 3 Actions Before Signing",
    ]

    for i, action in enumerate(top_3, 1):
        lines.append(f"{i}. {action}")

    info_count = summary.total_clauses - summary.critical_count - summary.high_count - summary.medium_count - summary.low_count

    lines.extend([
        "",
        "## Risk Summary",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 Critical | {summary.critical_count} |",
        f"| 🟠 High | {summary.high_count} |",
        f"| 🟡 Medium | {summary.medium_count} |",
        f"| 🟢 Low | {summary.low_count} |",
        f"| ℹ️ Info | {max(info_count, 0)} |",
        "",
        "---",
        "",
        "## Clause Analysis",
        "",
    ])

    for sc in scored_clauses:
        emoji = _severity_emoji(sc.finding.severity)
        lines.append(
            f"### {sc.clause.clause_type.value} — {emoji} {sc.finding.severity.value}"
        )
        lines.append(f"**Original:** {sc.clause.raw_text}")
        if sc.clause.plain_english:
            lines.append(f"**Plain English:** {sc.clause.plain_english}")
        lines.append(f"**Risk:** {sc.finding.risk_reason}")
        if sc.finding.recommended_action:
            lines.append(f"**Action:** {sc.finding.recommended_action}")
        lines.append("")

    return "\n".join(lines)


def _build_executive_summary_text(
    scored_clauses: List[ScoredClause], summary: RiskSummary
) -> str:
    """Build a brief executive summary of the main risks."""
    high_severity = [sc for sc in scored_clauses if sc.finding.severity in (Severity.CRITICAL, Severity.HIGH)]

    if not high_severity:
        return (
            "This contract appears to be reasonably balanced with no critical or high-risk clauses identified. "
            "Review the medium-risk findings below for items that may warrant attention."
        )

    types_found = list({sc.clause.clause_type.value for sc in high_severity})
    types_str = ", ".join(types_found)

    return (
        f"This contract contains {summary.critical_count} critical and {summary.high_count} high-severity risks "
        f"that require immediate attention. The most concerning areas involve: {types_str}. "
        f"We strongly recommend addressing the top 3 actions below before signing this agreement."
    )


def _severity_emoji(severity: Severity) -> str:
    """Return emoji for severity level."""
    emoji_map = {
        Severity.CRITICAL: "🔴",
        Severity.HIGH: "🟠",
        Severity.MEDIUM: "🟡",
        Severity.LOW: "🟢",
        Severity.INFO: "ℹ️",
    }
    return emoji_map.get(severity, "⚪")
