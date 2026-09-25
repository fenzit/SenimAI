from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    FACTUAL = "factual"
    NUMERICAL = "numerical"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"
    OPINION = "opinion"


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNVERIFIED = "UNVERIFIED"
    NOT_FACT_CHECKABLE = "NOT_FACT_CHECKABLE"
    CONFLICTING = "CONFLICTING"


class SourceTier(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Source(BaseModel):
    title: str = Field(..., description="Page or article title")
    url: str = Field(..., description="Link to source")
    domain: str = Field(..., description="Domain name (e.g. wikipedia.org)")
    snippet: str = Field(..., description="Extracted relevant text excerpt")
    quality: SourceTier = Field(default=SourceTier.MEDIUM, description="Heuristic quality tier")


class SupportingEvidence(BaseModel):
    source_index: int = Field(..., description="1-based index corresponding to sources list")
    reason: str = Field(..., description="How this source relates to the claim")


class Claim(BaseModel):
    id: int
    text: str = Field(..., description="Atomic extracted claim")
    type: ClaimType = Field(default=ClaimType.FACTUAL, description="Category of claim")


class ClaimResult(BaseModel):
    id: int
    text: str
    type: ClaimType
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0, description="Verification confidence score")
    explanation: str = Field(..., description="Human-readable explanation of why this verdict was chosen")
    sources: List[Source] = Field(default_factory=list, description="External sources evaluated")
    supporting_evidence: Optional[List[SupportingEvidence]] = Field(
        default=None, description="Detailed source breakdown"
    )
