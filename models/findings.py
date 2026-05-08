"""Pydantic models for risk findings and scored clauses."""

from enum import Enum

from pydantic import BaseModel, Field

from clauseguard.models.clause import Clause


class Severity(str, Enum):
    """Enumeration of risk severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RecommendedAction(BaseModel):
    """A specific, actionable recommendation for a clause."""

    action: str = Field(..., description="What to do (e.g., negotiate, remove, clarify)")
    sample_counter_language: str = Field(
        default="", description="Suggested alternative language for negotiation"
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Action priority: 1=do immediately, 2=strongly recommend, 3=consider",
    )


class RiskFinding(BaseModel):
    """A risk finding associated with a specific clause."""

    clause_id: int = Field(..., description="The ID of the clause this finding relates to")
    severity: Severity = Field(..., description="Severity level of the risk")
    risk_title: str = Field(..., description="Short title describing the risk")
    risk_reason: str = Field(
        ..., description="Detailed explanation citing what the clause actually says"
    )
    recommended_action: str = Field(
        default="", description="Specific, actionable recommendation"
    )
    negotiation_tip: str = Field(
        default="",
        description="Suggested counter-language or negotiation approach for this clause",
    )
    safer_clause_version: str = Field(
        default="",
        description="A rewritten, safer version of the clause to propose",
    )
    negotiation_message: str = Field(
        default="",
        description="Email-style message the user can copy-paste to request the change",
    )
    impact_scenarios: list[str] = Field(
        default_factory=list,
        description="2-3 realistic consequences if the user signs this clause as-is",
    )


class ScoredClause(BaseModel):
    """A clause paired with its risk finding."""

    clause: Clause = Field(..., description="The original clause")
    finding: RiskFinding = Field(..., description="The associated risk finding")
