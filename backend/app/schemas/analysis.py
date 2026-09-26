from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.claim import ClaimResult


class AnalyzeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="The AI response or text to verify",
        examples=["Python был создан Гвидо ван Россумом в 1991 году в Лондоне."],
    )
    language: str = Field(
        default="ru",
        description="Preferred language for explanations ('ru', 'en', 'kz')",
    )
    max_claims: int = Field(
        default=8,
        ge=1,
        le=15,
        description="Maximum number of atomic claims to extract and verify",
    )


class Summary(BaseModel):
    total_claims: int = Field(..., description="Total number of claims analyzed")
    supported: int = Field(0, description="Claims supported by external evidence")
    contradicted: int = Field(0, description="Claims contradicted by external evidence")
    partially_supported: int = Field(0, description="Claims with mixed/partial support")
    unverified: int = Field(0, description="Claims without sufficient external evidence")
    not_fact_checkable: int = Field(0, description="Subjective opinions or non-verifiable statements")
    conflicting: int = Field(0, description="Claims where reliable sources contradict each other")
    verification_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Evidence coverage score between 0.0 and 1.0 (0% to 100%)",
    )
    high_quality_sources_count: int = Field(
        default=0, description="Number of reputable high-tier sources used in verification"
    )
    average_confidence: float = Field(
        default=0.0, description="Average verification confidence across all claims"
    )


class AnalyzeResponse(BaseModel):
    analysis_id: str = Field(..., description="Unique UUID for this analysis session")
    summary: Summary
    claims: List[ClaimResult]
    original_text: Optional[str] = Field(default=None, description="Original input text")
    processing_time_ms: Optional[float] = Field(
        default=None, description="End-to-end processing latency in milliseconds"
    )
    timestamp: Optional[str] = Field(
        default=None, description="ISO timestamp of analysis"
    )
