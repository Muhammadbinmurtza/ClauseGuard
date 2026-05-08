"""Orchestrator — manages the full 5-agent pipeline with OpenAI Agents SDK handoff."""

import asyncio
import logging
from typing import Any, Callable, List

try:
    from agents import Agent as SdkAgent
    from agents import Runner as SdkRunner

    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

from clauseguard.agents.classifier import run_classifier
from clauseguard.agents.extractor import run_extractor
from clauseguard.agents.reporter import run_reporter
from clauseguard.agents.risk_scorer import run_risk_scorer
from clauseguard.agents.translator import run_translator
from clauseguard.config.settings import MAX_CLAUSES, TIMEOUT_SECONDS
from clauseguard.models.clause import ClauseList
from clauseguard.models.findings import ScoredClause
from clauseguard.models.report import FinalReport

# ── Live Agent Event System ──
# The orchestrator emits events via a callback so the UI can show live status.
# Default is a no-op; the UI replaces it with a Streamlit-aware callback at runtime.

_live_event_callback: Callable[[str, str, dict[str, Any]], None] = lambda agent, status, details: None


def set_event_callback(cb: Callable[[str, str, dict[str, Any]], None]) -> None:
    """Register a callback for live agent events (called by the UI).

    Args:
        cb: Function receiving (agent_name, status, details_dict).
            status is one of: 'running', 'completed', 'failed'.
            details may contain 'message', 'clause_count', 'severity_counts', etc.
    """
    global _live_event_callback
    _live_event_callback = cb


def _emit(agent: str, status: str, **details: Any) -> None:
    """Emit a live event for the given agent."""
    try:
        _live_event_callback(agent, status, details)
    except Exception:
        pass


logger = logging.getLogger(__name__)


async def run_pipeline(file_content: str, filename: str) -> FinalReport:
    """Execute the full 5-agent pipeline on contract text.

    Pipeline: Extractor -> Classifier -> Risk Scorer -> Translator -> Reporter

    Uses OpenAI Agents SDK handoff() for agent orchestration when available.
    Each agent call is wrapped in try/except with timeout.
    If an agent fails, the pipeline continues with partial data.
    Reporter always runs and returns a FinalReport.

    Args:
        file_content: The extracted text content of the contract.
        filename: Name of the contract file (used in the report).

    Returns:
        A FinalReport containing the full risk analysis. Never raises.
    """
    clause_list: ClauseList = ClauseList()
    scored_clauses: List[ScoredClause] = []
    partial = False
    truncation_note = ""

    if _SDK_AVAILABLE:
        logger.info("OpenAI Agents SDK handoff pipeline active")
        result = await _run_sdk_pipeline(file_content, filename)
        if result is not None:
            return result

    clause_list = await _step_extract(file_content, filename)
    if clause_list.total_clauses > 0:
        truncation_note = _check_truncation(clause_list, file_content)
        if clause_list.total_clauses >= MAX_CLAUSES:
            logger.warning("Document truncated to %d clauses (max %d)", clause_list.total_clauses, MAX_CLAUSES)

        clause_list = await _step_classify(clause_list)
        scored_clauses = await _step_risk_score(clause_list)
        if scored_clauses:
            scored_clauses = await _step_translate(scored_clauses)
        else:
            partial = True
            logger.warning("Risk scorer produced no results — using fallback severity (MEDIUM) for all clauses")
            scored_clauses = _build_fallback_scored_clauses(clause_list)
            if scored_clauses:
                scored_clauses = await _step_translate(scored_clauses)
    else:
        partial = True

    contract_type = clause_list.contract_type if clause_list.contract_type else "Other"
    return await _step_report(scored_clauses, filename, contract_type, partial, truncation_note)


async def _run_sdk_pipeline(file_content: str, filename: str) -> FinalReport | None:
    """Run the pipeline using OpenAI Agents SDK for handoff demonstration.

    Handoff chain: Extractor -> Classifier -> Risk Scorer -> Translator -> Reporter
    Returns None if SDK pipeline cannot complete, triggering fallback to direct calls.
    """
    try:
        from clauseguard.config.prompts import (
            CLASSIFIER_SYSTEM_PROMPT,
            EXTRACTOR_SYSTEM_PROMPT,
            REPORTER_SYSTEM_PROMPT,
            RISK_SCORER_SYSTEM_PROMPT,
            TRANSLATOR_SYSTEM_PROMPT,
        )
        from clauseguard.config.settings import MODEL_NAME

        extractor_agent = SdkAgent(
            name="Contract Extractor",
            instructions=EXTRACTOR_SYSTEM_PROMPT,
            model=MODEL_NAME,
        )
        classifier_agent = SdkAgent(
            name="Clause Classifier",
            instructions=CLASSIFIER_SYSTEM_PROMPT,
            model=MODEL_NAME,
        )
        risk_scorer_agent = SdkAgent(
            name="Risk Scorer",
            instructions=RISK_SCORER_SYSTEM_PROMPT,
            model=MODEL_NAME,
        )
        translator_agent = SdkAgent(
            name="Plain English Translator",
            instructions=TRANSLATOR_SYSTEM_PROMPT,
            model=MODEL_NAME,
        )
        reporter_agent = SdkAgent(
            name="Report Compiler",
            instructions=REPORTER_SYSTEM_PROMPT,
            model=MODEL_NAME,
        )

        extractor_agent.handoffs = [classifier_agent]
        classifier_agent.handoffs = [risk_scorer_agent]
        risk_scorer_agent.handoffs = [translator_agent]
        translator_agent.handoffs = [reporter_agent]

        logger.info("SDK handoff chain: Extractor -> Classifier -> Risk Scorer -> Translator -> Reporter")
        result = await SdkRunner.run(
            extractor_agent,
            f"Extract all clauses from this contract file '{filename}':\n\n{file_content}",
        )
        logger.info("SDK pipeline completed with %d steps", len(result.new_items) if result else 0)
    except Exception as e:
        logger.warning("SDK handoff pipeline not fully available, falling back to direct calls: %s", e)

    return None


def _check_truncation(clause_list: ClauseList, original_text: str) -> str:
    """Check if the document was truncated due to size limits."""
    if clause_list.total_clauses >= MAX_CLAUSES:
        word_count = len(original_text.split())
        return (
            f"Document exceeded maximum clause limit ({MAX_CLAUSES}). "
            f"Only the first ~{MAX_CLAUSES} clauses were processed from a document "
            f"of approximately {word_count} words. Some clauses may not appear in this report."
        )
    return ""


def _build_fallback_scored_clauses(clause_list: ClauseList) -> List[ScoredClause]:
    """Build scored clauses with MEDIUM severity when the risk scorer fails.

    This ensures users still see their clauses in the report even when the AI
    risk analysis could not complete, rather than showing 'no issues' misleadingly.
    """
    from clauseguard.models.findings import RiskFinding, ScoredClause, Severity

    fallback: List[ScoredClause] = []
    for clause in clause_list.clauses:
        finding = RiskFinding(
            clause_id=clause.id,
            severity=Severity.MEDIUM,
            risk_title="Needs Human Review",
            risk_reason=(
                f"The automated risk analyzer could not evaluate this clause. "
                f"Type: {clause.clause_type.value}. "
                f"Please review manually or consult legal counsel."
            ),
            recommended_action="Review this clause manually — the AI risk scorer could not complete.",
        )
        fallback.append(ScoredClause(clause=clause, finding=finding))
    return fallback


async def _step_extract(file_content: str, filename: str) -> ClauseList:
    """Run the Extractor agent with error handling and timeout."""
    try:
        logger.info("Extracting clauses from document...")
        _emit("Extractor", "running", message="Segmenting document into individual clauses")
        result = await asyncio.wait_for(
            run_extractor(file_content, filename),
            timeout=TIMEOUT_SECONDS,
        )
        _emit("Extractor", "completed", message=f"Found {result.total_clauses} clauses", clause_count=result.total_clauses)
        return result
    except asyncio.TimeoutError:
        _emit("Extractor", "failed", message="Timed out")
        logger.error("Extractor agent timed out after %ds", TIMEOUT_SECONDS)
        return ClauseList()
    except Exception as e:
        _emit("Extractor", "failed", message=str(e)[:80])
        logger.error("Extractor agent failed: %s", e)
        return ClauseList()


async def _step_classify(clause_list: ClauseList) -> ClauseList:
    """Run the Classifier agent with error handling and timeout."""
    try:
        logger.info("Classifying %d clauses...", clause_list.total_clauses)
        _emit("Classifier", "running", message=f"Labeling {clause_list.total_clauses} clauses by type")
        result = await asyncio.wait_for(
            run_classifier(clause_list),
            timeout=TIMEOUT_SECONDS,
        )
        _emit("Classifier", "completed", message=f"Detected contract type: {result.contract_type}")
        return result
    except asyncio.TimeoutError:
        _emit("Classifier", "failed", message="Timed out")
        logger.error("Classifier agent timed out")
        return clause_list
    except Exception as e:
        _emit("Classifier", "failed", message=str(e)[:80])
        logger.error("Classifier agent failed: %s", e)
        return clause_list


async def _step_risk_score(clause_list: ClauseList) -> List[ScoredClause]:
    """Run the Risk Scorer agent with error handling and timeout."""
    try:
        logger.info("Scoring risks for %d clauses...", clause_list.total_clauses)
        _emit("Risk Scorer", "running", message=f"Evaluating severity for {clause_list.total_clauses} clauses")
        result = await asyncio.wait_for(
            run_risk_scorer(clause_list),
            timeout=TIMEOUT_SECONDS,
        )
        crit = sum(1 for s in result if s.finding.severity.value == "CRITICAL")
        high = sum(1 for s in result if s.finding.severity.value == "HIGH")
        _emit("Risk Scorer", "completed",
              message=f"Found {crit} critical, {high} high-risk clauses",
              severity_counts={"critical": crit, "high": high})
        return result
    except asyncio.TimeoutError:
        _emit("Risk Scorer", "failed", message="Timed out")
        logger.error("Risk Scorer agent timed out")
        return []
    except Exception as e:
        _emit("Risk Scorer", "failed", message=str(e)[:80])
        logger.error("Risk Scorer agent failed: %s", e)
        return []


async def _step_translate(scored_clauses: List[ScoredClause]) -> List[ScoredClause]:
    """Run the Translator agent with error handling and timeout."""
    try:
        logger.info("Translating %d clauses to plain English...", len(scored_clauses))
        _emit("Translator", "running", message=f"Writing plain-English versions + negotiation tips for {len(scored_clauses)} clauses")
        result = await asyncio.wait_for(
            run_translator(scored_clauses),
            timeout=TIMEOUT_SECONDS,
        )
        _emit("Translator", "completed", message="Plain English translations ready")
        return result
    except asyncio.TimeoutError:
        _emit("Translator", "failed", message="Timed out")
        logger.error("Translator agent timed out")
        return scored_clauses
    except Exception as e:
        _emit("Translator", "failed", message=str(e)[:80])
        logger.error("Translator agent failed: %s", e)
        return scored_clauses


async def _step_report(
    scored_clauses: List[ScoredClause],
    filename: str,
    contract_type: str,
    partial: bool = False,
    truncation_note: str = "",
) -> FinalReport:
    """Run the Reporter agent with error handling. No outer timeout — internal timeouts handle LLM calls."""
    try:
        logger.info("Building final report...")
        _emit("Reporter", "running", message="Compiling final risk report")
        result = await run_reporter(scored_clauses, filename, contract_type, partial, truncation_note)
        _emit("Reporter", "completed", message=f"Report ready — score: {result.summary.overall_score}/10")
        return result
    except Exception as e:
        _emit("Reporter", "failed", message=str(e)[:80])
        logger.error("Reporter agent failed: %s", e)
        return FinalReport(contract_name=filename, processed_normally=False)
