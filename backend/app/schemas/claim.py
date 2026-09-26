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
    NUANCED = "NUANCED"
    UNVERIFIED = "UNVERIFIED"
    NOT_FACT_CHECKABLE = "NOT_FACT_CHECKABLE"
    CONFLICTING = "CONFLICTING"


class SourceTier(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SourceStance(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceSufficiency(str, Enum):
    DIRECT = "DIRECT"
    COMBINED = "COMBINED"
    INDIRECT = "INDIRECT"
    INSUFFICIENT = "INSUFFICIENT"


class Source(BaseModel):
    title: str = Field(..., description="Page or article title")
    url: str = Field(..., description="Link to source")
    domain: str = Field(..., description="Domain name (e.g. wikipedia.org)")
    snippet: str = Field(..., description="Extracted relevant text excerpt")
    quality: SourceTier = Field(default=SourceTier.MEDIUM, description="Heuristic quality tier")
    stance: Optional[SourceStance] = Field(
        default=SourceStance.NEUTRAL, description="Source stance towards claim"
    )
    published_date: Optional[str] = Field(
        default=None, description="Publication or index date if available"
    )
    freshness_label: Optional[str] = Field(
        default=None, description="Human readable freshness (e.g., 'Recent', '2024', 'Archival')"
    )


class SupportingEvidence(BaseModel):
    source_index: int = Field(..., description="1-based index corresponding to sources list")
    reason: str = Field(..., description="How this source relates to the claim")


class Claim(BaseModel):
    id: int
    text: str = Field(..., description="Atomic extracted claim")
    type: ClaimType = Field(default=ClaimType.FACTUAL, description="Category of claim")
    original_quote: Optional[str] = Field(
        default=None, description="Verbatim quote or excerpt from the original text"
    )
    start_char: Optional[int] = Field(default=None, description="Start offset in original text")
    end_char: Optional[int] = Field(default=None, description="End offset in original text")
    causal_role: Optional[str] = Field(
        default="STANDALONE",
        description="'PREMISE' | 'DEDUCTION' | 'STANDALONE'",
    )


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
    original_quote: Optional[str] = Field(
        default=None, description="Verbatim excerpt in original text for frontend highlighting"
    )
    start_char: Optional[int] = Field(default=None, description="Start offset in original text")
    end_char: Optional[int] = Field(default=None, description="End offset in original text")
    why_verdict: Optional[str] = Field(
        default=None, description="Detailed explainability breakdown for 'Ask Why' feature"
    )
    evidence_sufficiency: Optional[EvidenceSufficiency] = Field(
        default=EvidenceSufficiency.DIRECT,
        description="DIRECT (single source), COMBINED (multi-hop synthesis), INDIRECT, or INSUFFICIENT",
    )
    causal_role: Optional[str] = Field(
        default="STANDALONE",
        description="'PREMISE' | 'DEDUCTION' | 'STANDALONE'",
    )

