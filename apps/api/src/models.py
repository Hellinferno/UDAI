import re
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Constrained scalar types reused across schemas
# ---------------------------------------------------------------------------

DealTypeStr = Literal[
    "ipo", "ma", "lbo", "debt_raise", "equity_raise",
    "restructuring", "merger", "acquisition", "secondary",
    "private_placement", "other"
]

DealStageStr = Literal[
    "preliminary", "in_progress", "due_diligence", "final", "closed"
]

PriorityStr = Literal["low", "medium", "high"]

ReviewStatusStr = Literal["draft", "in_review", "approved", "rejected"]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: Optional[str]) -> Optional[str]:
    """Remove HTML tags from a string to prevent XSS if notes are ever rendered."""
    if value is None:
        return None
    return _HTML_TAG_RE.sub("", value).strip()


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class DealCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    company_name: str = Field(..., min_length=1, max_length=80)
    deal_type: DealTypeStr
    industry: str = Field(..., min_length=1, max_length=60)
    deal_stage: DealStageStr = "preliminary"
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("name", "company_name", "industry", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v):
        return _strip_html(v)


class DealUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    company_name: Optional[str] = Field(None, min_length=1, max_length=80)
    deal_type: Optional[DealTypeStr] = None
    industry: Optional[str] = Field(None, min_length=1, max_length=60)
    deal_stage: Optional[DealStageStr] = None
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("name", "company_name", "industry", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v):
        return _strip_html(v)


class AgentRunCreate(BaseModel):
    agent_type: str = Field(..., min_length=1, max_length=40)
    task_name: str = Field(..., min_length=1, max_length=80)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    owner: Optional[str] = Field(None, max_length=80)
    priority: PriorityStr = "medium"
    due_date: Optional[str] = None


class OutputReviewUpdate(BaseModel):
    review_status: ReviewStatusStr
    reviewer_notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("reviewer_notes", mode="before")
    @classmethod
    def sanitize_reviewer_notes(cls, v):
        return _strip_html(v)


# ---------------------------------------------------------------------------
# Response Envelopes
# ---------------------------------------------------------------------------

class Meta(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    request_id: str


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    meta: Meta


class APIResponseList(BaseModel):
    success: bool
    data: Dict[str, Any]  # e.g. {"deals": [...], "total": 1, "limit": 20, "offset": 0}
    error: Optional[Dict[str, Any]] = None
    meta: Meta
