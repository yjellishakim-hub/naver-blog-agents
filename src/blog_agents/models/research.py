from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ContentCategory(str, Enum):
    MACRO_FINANCE = "macro_finance"
    REAL_ESTATE_TAX = "real_estate_tax"
    CORPORATE_FAIR = "corporate_fair"

    @property
    def display_name(self) -> str:
        names = {
            "macro_finance": "거시경제·금융정책",
            "real_estate_tax": "부동산·세법",
            "corporate_fair": "기업법·공정거래",
        }
        return names[self.value]


class SourceType(str, Enum):
    GOVERNMENT_PRESS = "government_press"
    RSS_NEWS = "rss_news"
    LAW_API = "law_api"
    WEB_SEARCH = "web_search"


class Source(BaseModel):
    title: str
    url: str
    source_type: SourceType
    publisher: str
    published_date: Optional[str] = None
    snippet: str = ""
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.5)


class TopicSuggestion(BaseModel):
    title: str = Field(description="제안하는 블로그 포스트 제목")
    category: ContentCategory
    angle: str = Field(description="이 주제를 다루는 독특한 관점/각도")
    timeliness: str = Field(description="지금 이 주제를 다뤄야 하는 이유")
    target_keywords: list[str] = Field(description="SEO 타겟 키워드 3-5개")
    estimated_interest: float = Field(
        ge=0.0, le=1.0, description="예상 독자 관심도 (0-1)"
    )


class TopicSuggestionList(BaseModel):
    topics: list[TopicSuggestion]


class ResearchBrief(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    category: ContentCategory
    topic: TopicSuggestion
    sources: list[Source] = Field(default_factory=list)
    background_context: str = Field(
        default="", description="주제의 배경 맥락 (2-3 문단)"
    )
    key_facts: list[str] = Field(
        default_factory=list, description="핵심 팩트 5개 이상"
    )
    legal_references: list[str] = Field(
        default_factory=list, description="관련 법령명과 조항"
    )
    expert_opinions: list[str] = Field(
        default_factory=list, description="전문가 의견/입장"
    )
    data_points: list[str] = Field(
        default_factory=list, description="통계 수치와 데이터"
    )
    related_topics: list[str] = Field(
        default_factory=list, description="관련 주제 (내부 링킹용)"
    )


class ResearchBriefOutput(BaseModel):
    """리서치 에이전트의 구조화된 출력 모델."""

    background_context: str
    key_facts: list[str]
    legal_references: list[str]
    expert_opinions: list[str]
    data_points: list[str]
    related_topics: list[str]
