"""Pydantic models for the Story Engine pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Step 0 – Problem Framing
# ---------------------------------------------------------------------------

class SubQuestion(BaseModel):
    id: str = Field(..., description="e.g. '1.1', '2.3'")
    question: str


class MECESection(BaseModel):
    section_id: int
    title: str
    rationale: str = Field(..., description="Why this section is necessary")
    questions: list[SubQuestion]


class ProblemStatement(BaseModel):
    topic: str
    audience: str
    smart_statement: str = Field(
        ...,
        description="SMART problem statement: What steps do X need to take to Y given Z",
    )
    sections: list[MECESection]
    revision_history: list[str] = Field(
        default_factory=list,
        description="Human feedback incorporated across iterations",
    )


# ---------------------------------------------------------------------------
# Step 1 – Research
# ---------------------------------------------------------------------------

class ResearchPrompt(BaseModel):
    section_id: int
    section_title: str
    prompt: str
    questions_covered: list[str]


class ResearchCompilation(BaseModel):
    sections: list[ResearchSection]


class ResearchSection(BaseModel):
    section_id: int
    section_title: str
    content: str


# ---------------------------------------------------------------------------
# Step 2 – Working Document
# ---------------------------------------------------------------------------

class AnalystView(BaseModel):
    analyst_label: str = Field(..., description="e.g. 'Bull case', 'Bear case'")
    summary: str


class WorkingDocumentSection(BaseModel):
    section_id: int
    title: str
    body: str
    key_findings: list[str]


class WorkingDocument(BaseModel):
    title: str
    executive_summary: str
    sections: list[WorkingDocumentSection]
    analyst_compare_contrast: list[AnalystView]


# ---------------------------------------------------------------------------
# Step 3 – Card Decomposition
# ---------------------------------------------------------------------------

class ActLabel(str, Enum):
    SITUATION = "1"
    REFINERY_CEO = "2a"
    CFO = "2b"
    POLICY = "2c"
    BOARD = "2d"
    EDGE = "3"


class CardType(str, Enum):
    HERO = "hero"
    TIMELINE = "timeline"
    KPI = "kpi"
    VERDICT_PANEL = "verdict_panel"
    SCENARIO = "scenario"
    CHECKLIST = "checklist"
    CHART = "chart"
    MAP = "map"
    QUOTE_PAIR = "quote_pair"
    ACT_BREAK = "act_break"
    CLOSING = "closing"


class Relationship(str, Enum):
    CAUSE_EFFECT = "cause_effect"
    BEFORE_AFTER = "before_after"
    COMPARE_CONTRAST = "compare_contrast"
    PARALLEL = "parallel"
    ESCALATING = "escalating"


class VisualType(str, Enum):
    BIG_NUMBER = "big_number"
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    SCATTER = "scatter"
    MAP = "map"
    TEXT = "text"
    BARS = "bars"


class SubMessage(BaseModel):
    text: str
    visual_weight: str = Field(..., description="e.g. '1/4', '3/4', '1/2'")
    visual_type: VisualType
    chart_type: Optional[str] = Field(
        None, description="Specific chart subtype when visual_type is chart"
    )


class CardSpec(BaseModel):
    card_id: str
    act: ActLabel
    card_type: CardType
    key_message: str = Field(..., description="Single sentence")
    sub_messages: list[SubMessage] = Field(
        ..., min_length=2, max_length=3,
    )
    relationship: Relationship
    visual_decision: str = Field(
        ...,
        description="Reasoning for the visual choices applied to sub_messages",
    )
    data: dict = Field(
        ...,
        description="Actual numbers, quotes, facts for the card",
    )
    source: str = Field(..., description="Attribution line")


class CardDeck(BaseModel):
    topic: str
    audience: str
    cards: list[CardSpec]


# ---------------------------------------------------------------------------
# Pipeline state (for --resume)
# ---------------------------------------------------------------------------

class PipelineState(BaseModel):
    topic: str
    audience: str
    last_completed_step: int = Field(
        -1, description="Last fully completed step (-1 = none)"
    )
