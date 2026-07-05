"""Pydantic models for the final risk report."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from clauseguard.models.findings import ScoredClause


class ClauseReport(BaseModel):
    """Per-clause analysis record within the final report."""

    clause_number: int = Field(..., description="1-based index of clause in report")
    clause_type: str = Field(..., description="Classified type of this clause")
    severity: str = Field(..., description="Severity rating")
    severity_emoji: str = Field(..., description="Emoji for severity level")
    raw_text: str = Field(..., description="Original clause text")
    plain_english: str = Field("", description="Plain English translation")
    risk_title: str = Field(..., description="Risk title")
    risk_reason: str = Field(..., description="Why this is a risk")
    recommended_action: str = Field("", description="What to do about it")
    negotiation_tip: Optional[str] = Field(
        None, description="Suggested counter-language for negotiation"
    )


class RiskSummary(BaseModel):
    """Summary statistics for a risk report."""

    total_clauses: int = Field(0, description="Total number of clauses analyzed")
    critical_count: int = Field(0, description="Number of CRITICAL findings")
    high_count: int = Field(0, description="Number of HIGH findings")
    medium_count: int = Field(0, description="Number of MEDIUM findings")
    low_count: int = Field(0, description="Number of LOW findings")
    overall_score: float = Field(
        0.0, description="Overall risk score from 0 to 10 (10 = most risky)"
    )
    contract_type: str = Field(
        "Other", description="The detected type of contract"
    )


class FinalReport(BaseModel):
    """The complete ClauseGuard risk analysis report."""

    contract_name: str = Field(..., description="Name of the analyzed contract file")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the report was generated"
    )
    summary: RiskSummary = Field(
        default_factory=RiskSummary, description="Risk summary statistics"
    )
    top_3_actions: List[str] = Field(
        default_factory=list, description="Top 3 recommended actions before signing"
    )
    scored_clauses: List[ScoredClause] = Field(
        default_factory=list, description="All scored clauses ordered by severity"
    )
    markdown_report: str = Field(
        "", description="The full report formatted as markdown"
    )
    processed_normally: bool = Field(
        True,
        description="False if the pipeline was truncated or ran with partial data",
    )
    truncation_note: str = Field(
        "", description="Note about truncation if contract exceeded clause limit"
    )
    error_message: str = Field(
        "", description="Error message if the pipeline failed partially or fully"
    )
