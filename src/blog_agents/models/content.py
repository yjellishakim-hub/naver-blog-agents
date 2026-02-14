from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from blog_agents.models.research import ContentCategory, Source


class Section(BaseModel):
    heading: str
    content: str
    heading_level: int = Field(ge=2, le=4, default=2)


class DraftMetadata(BaseModel):
    """작가 에이전트가 생성하는 메타데이터."""

    title: str = Field(description="블로그 포스트 제목")
    meta_description: str = Field(
        description="SEO 메타 설명 (155자 이내)", max_length=200
    )
    keywords: list[str] = Field(description="사용된 키워드 목록")
    estimated_read_time_minutes: int = Field(
        description="예상 읽기 시간 (분)", ge=1, le=30
    )


class Draft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    research_brief_id: str = ""
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    category: ContentCategory = ContentCategory.MACRO_FINANCE
    title: str = ""
    meta_description: str = ""
    keywords_used: list[str] = Field(default_factory=list)
    estimated_read_time_minutes: int = 5
    full_markdown: str = ""
    sources_cited: list[Source] = Field(default_factory=list)


class BlogPost(BaseModel):
    """최종 승인된 발행 가능 포스트."""

    draft: Draft
    final_score: float
    approved_at: datetime = Field(default_factory=datetime.now)
    editor_notes: str = ""
    html_content: Optional[str] = None

    @property
    def frontmatter(self) -> dict:
        return {
            "title": self.draft.title,
            "date": self.draft.created_at.strftime("%Y-%m-%d"),
            "category": self.draft.category.value,
            "keywords": self.draft.keywords_used,
            "meta_description": self.draft.meta_description,
            "quality_score": self.final_score,
            "revision_rounds": self.draft.version,
        }
