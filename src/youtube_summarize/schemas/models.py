"""Pydantic models for structured video summaries."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Outcome = Literal["success", "failure", "mixed", "unknown"]
Confidence = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    timestamp: str = Field(description="MM:SS, HH:MM:SS, or 'N/A' if not available.")
    snippet: str = Field(description="<= 20 words from the video (paraphrase allowed).")
    note: Optional[str] = Field(default=None, description="Extra context if needed.")


class Metric(BaseModel):
    metric_type: Literal[
        "revenue",
        "profit",
        "spend",
        "burn",
        "funding",
        "valuation",
        "users",
        "paying_customers",
        "mau",
        "dau",
        "downloads",
        "price",
        "arr",
        "mrr",
        "growth_rate",
        "churn",
        "cac",
        "ltv",
        "other",
    ]
    value: Optional[float] = Field(default=None, description="Numeric value if explicitly stated; else null.")
    unit: Optional[str] = Field(default=None, description="e.g., USD, users, %, downloads, etc.")
    time_frame: Optional[str] = Field(default=None, description="e.g., 'per month', 'ARR', 'as of 2025', etc.")
    confidence: Confidence = Field(description="high if exact, medium if approximate, low if uncertain")
    evidence: List[Evidence] = Field(description="At least one evidence item for this metric.")


class Product(BaseModel):
    name: Optional[str] = Field(default=None, description="Product/company name if stated.")
    what_it_does: str = Field(description="What the product does.")
    target_customer: Optional[str] = None
    business_model: Optional[str] = None
    outcome: Outcome
    outcome_reasoning: str = Field(description="Why the outcome label was chosen (based on video statements).")
    status: Optional[Literal["active", "shutdown", "acquired", "pivoted", "unknown"]] = "unknown"
    competitors: List[str] = Field(default_factory=list, description="Only explicit mentions.")
    metrics: List[Metric] = Field(default_factory=list)
    key_lessons: List[str] = Field(default_factory=list)
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence for product description/outcome/competitors."
    )


class FounderStory(BaseModel):
    people: List[str] = Field(default_factory=list, description="Founders/guests names if stated.")
    background: Optional[str] = None
    attempts: List[str] = Field(default_factory=list, description="Prior attempts/pivots described.")
    themes: List[str] = Field(default_factory=list, description="Recurring themes (e.g., distribution, PMF).")


class VideoExtraction(BaseModel):
    video_url: str
    title: Optional[str] = ""
    channel: Optional[str] = ""
    upload_date: Optional[str] = Field(default="", description="YYYY-MM-DD if known else empty string.")
    story: FounderStory
    products: List[Product]
    top_takeaways: List[str]
    missing_info: List[str] = Field(
        default_factory=list,
        description="Important fields the video did not provide (e.g., 'revenue', 'user count').",
    )
    limitations: List[str] = Field(default_factory=list, description="Caveats: timestamps missing, unclear audio.")
