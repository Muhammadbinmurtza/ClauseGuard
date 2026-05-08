"""Pydantic models for contract clauses."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ClauseType(str, Enum):
    """Enumeration of clause categories found in contracts."""

    NDA = "NDA"
    IP_ASSIGNMENT = "IP_ASSIGNMENT"
    NON_COMPETE = "NON_COMPETE"
    ARBITRATION = "ARBITRATION"
    AUTO_RENEWAL = "AUTO_RENEWAL"
    LIABILITY_CAP = "LIABILITY_CAP"
    TERMINATION = "TERMINATION"
    DATA_SHARING = "DATA_SHARING"
    GOVERNING_LAW = "GOVERNING_LAW"
    PAYMENT = "PAYMENT"
    INDEMNIFICATION = "INDEMNIFICATION"
    OTHER = "OTHER"


class Clause(BaseModel):
    """A single clause extracted from a contract."""

    id: int = Field(..., description="Unique clause identifier")
    raw_text: str = Field(..., description="Original text of the clause")
    plain_english: Optional[str] = Field(
        None, description="Plain English translation of the clause"
    )
    clause_type: ClauseType = Field(
        default=ClauseType.OTHER, description="Classified type of this clause"
    )
    section_heading: Optional[str] = Field(
        None, description="Detected section heading for this clause"
    )
    position: int = Field(
        ..., description="Sequential position of the clause in the document"
    )
    confidence_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Classifier confidence score (0.0 to 1.0) for the assigned clause type",
    )


class ClauseList(BaseModel):
    """A collection of clauses extracted from a contract."""

    clauses: List[Clause] = Field(
        default_factory=list, description="List of extracted clauses"
    )
    contract_type: str = Field(
        default="Other", description="Detected overall contract type"
    )
    total_clauses: int = Field(0, description="Total number of clauses extracted")
