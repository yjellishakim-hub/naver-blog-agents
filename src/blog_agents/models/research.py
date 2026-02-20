from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ContentCategory(str, Enum):
    SEOUL_EXHIBITION = "seoul_exhibition"
    GWANGJU_CULTURE = "gwangju_culture"
    K_CONTENT = "k_content"

    @property
    def display_name(self) -> str:
        names = {
            "seoul_exhibition": "서울 전시",
            "gwangju_culture": "광주 문화",
            "k_content": "K-콘텐츠",
        }
        return names[self.value]


class SourceType(str, Enum):
    MUSEUM_WEBSITE = "museum_website"
    ART_MEDIA = "art_media"
    EXHIBITION_AGGREGATOR = "exhibition_aggregator"
    RSS_NEWS = "rss_news"
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
    exhibition_info: list[str] = Field(
        default_factory=list,
        description="전시명, 장소, 기간, 입장료, 운영시간 등 기본 정보",
    )
    artist_info: list[str] = Field(
        default_factory=list,
        description="작가 약력, 작품세계, 흥미로운 뒷이야기",
    )
    artwork_highlights: list[str] = Field(
        default_factory=list,
        description="주요 작품명, 매체, 해석, 숨겨진 이야기",
    )
    expert_opinions: list[str] = Field(
        default_factory=list, description="큐레이터·평론가 의견/리뷰"
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
    exhibition_info: list[str]
    artist_info: list[str]
    artwork_highlights: list[str]
    expert_opinions: list[str]
    data_points: list[str]
    related_topics: list[str]

    @model_validator(mode="before")
    @classmethod
    def flatten_dict_lists(cls, data):
        """LLM이 list[str] 대신 list[dict]를 반환할 경우 자동 변환."""
        if not isinstance(data, dict):
            return data
        for field_name in [
            "key_facts", "exhibition_info", "artist_info",
            "artwork_highlights", "expert_opinions", "data_points",
            "related_topics",
        ]:
            items = data.get(field_name, [])
            if items and isinstance(items[0], dict):
                data[field_name] = [
                    " ".join(str(v) for v in item.values())
                    for item in items
                ]
        return data
