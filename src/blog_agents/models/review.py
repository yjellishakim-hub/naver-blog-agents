from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ScoreDimension(BaseModel):
    dimension: str = Field(description="평가 차원명")
    score: float = Field(ge=1.0, le=10.0, description="점수 (1-10)")
    feedback: str = Field(description="구체적 피드백")


class LineEdit(BaseModel):
    location: str = Field(description="수정 위치 (섹션/문단 설명)")
    original: str = Field(default="", description="원문")
    suggestion: str = Field(default="", description="수정 제안")
    reason: str = Field(description="수정 이유")


class EditReview(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    draft_id: str = ""
    draft_version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    overall_score: float = Field(ge=1.0, le=10.0, description="종합 점수")
    dimensions: list[ScoreDimension] = Field(
        default_factory=list, description="6개 차원별 평가"
    )
    approved: bool = Field(default=False, description="승인 여부")
    revision_instructions: Optional[str] = Field(
        default=None, description="수정 요청 사항 (비승인 시)"
    )
    line_edits: list[LineEdit] = Field(
        default_factory=list, description="구체적 라인 수정 제안"
    )
    strengths: list[str] = Field(
        default_factory=list, description="잘된 점"
    )

    @model_validator(mode="before")
    @classmethod
    def auto_approve(cls, data):
        """approved 필드가 없으면 overall_score >= 8.5 기준으로 자동 결정."""
        if isinstance(data, dict) and "approved" not in data:
            score = data.get("overall_score", 0)
            data["approved"] = score >= 8.5
        return data
