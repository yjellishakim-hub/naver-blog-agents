from __future__ import annotations

import json
from uuid import uuid4

from rich.console import Console

from blog_agents.agents.base import BaseAgent
from blog_agents.models.content import Draft, DraftMetadata
from blog_agents.models.research import ContentCategory, ResearchBrief
from blog_agents.models.review import EditReview

console = Console()

# 카테고리별 스타일 프롬프트 파일 매핑
STYLE_PROMPTS = {
    ContentCategory.MACRO_FINANCE: "writer_macro.md",
    ContentCategory.REAL_ESTATE_TAX: "writer_realestate.md",
    ContentCategory.CORPORATE_FAIR: "writer_corporate.md",
}


class WriterAgent(BaseAgent):
    """리서치 브리핑을 기반으로 전문적인 블로그 포스트를 작성하는 에이전트."""

    agent_name = "작가"

    def __init__(self, config):
        model = config.models.get("writer", "claude-sonnet-4-5-20250514")
        super().__init__(config, model=model)

    def write_draft(
        self,
        brief: ResearchBrief,
        version: int = 1,
        review: EditReview | None = None,
    ) -> Draft:
        """리서치 브리핑을 기반으로 블로그 초안을 작성한다."""
        console.print(
            f'\n[bold green]작가 에이전트: "{brief.topic.title}" 작성 (v{version})[/]'
        )

        # 프롬프트 조합: 기본 + 카테고리 스타일
        style_file = STYLE_PROMPTS.get(brief.category, "writer_macro.md")

        # 수정 요청이 있는 경우 프롬프트에 포함
        revision_instructions = ""
        line_edits = []
        if review and not review.approved:
            revision_instructions = review.revision_instructions or ""
            line_edits = [e.model_dump() for e in review.line_edits]

        base_prompt = self._load_prompt(
            "writer_agent.md",
            revision_instructions=revision_instructions,
            line_edits=line_edits,
        )
        style_prompt = self._load_prompt(style_file)
        system_prompt = base_prompt + "\n\n" + style_prompt

        # 리서치 브리핑을 사용자 메시지로 구성
        user_message = self._format_brief_for_writing(brief, version, review)

        # 블로그 본문 생성 (자유 형식 마크다운)
        markdown_body = self._call_text(
            system_prompt, user_message, max_tokens=6000
        )

        # 메타데이터 추출
        metadata = self._extract_metadata(markdown_body, brief)

        # Draft 객체 조립
        draft = Draft(
            id=str(uuid4()),
            research_brief_id=brief.id,
            version=version,
            category=brief.category,
            title=metadata.title,
            meta_description=metadata.meta_description,
            keywords_used=metadata.keywords,
            estimated_read_time_minutes=metadata.estimated_read_time_minutes,
            full_markdown=markdown_body,
            sources_cited=brief.sources,
        )

        word_count = len(markdown_body)
        console.print(
            f"  [green]초안 v{version} 완료 ({word_count}자, "
            f"읽기 {draft.estimated_read_time_minutes}분)[/]"
        )
        return draft

    def _format_brief_for_writing(
        self,
        brief: ResearchBrief,
        version: int,
        review: EditReview | None,
    ) -> str:
        """리서치 브리핑을 작가가 사용하기 좋은 형식으로 포맷팅."""
        parts = [
            f"# 리서치 브리핑: {brief.topic.title}",
            f"\n## 카테고리: {brief.category.display_name}",
            f"\n## 작성 관점\n{brief.topic.angle}",
            f"\n## 시의성\n{brief.topic.timeliness}",
            f"\n## 타겟 키워드\n{', '.join(brief.topic.target_keywords)}",
            f"\n## 배경\n{brief.background_context}",
        ]

        if brief.key_facts:
            parts.append("\n## 핵심 팩트")
            for fact in brief.key_facts:
                parts.append(f"- {fact}")

        if brief.legal_references:
            parts.append("\n## 관련 법령")
            for ref in brief.legal_references:
                parts.append(f"- {ref}")

        if brief.expert_opinions:
            parts.append("\n## 전문가 의견")
            for opinion in brief.expert_opinions:
                parts.append(f"- {opinion}")

        if brief.data_points:
            parts.append("\n## 데이터/통계")
            for dp in brief.data_points:
                parts.append(f"- {dp}")

        if brief.sources:
            parts.append("\n## 참고 출처")
            for src in brief.sources[:10]:
                parts.append(f"- {src.title} ({src.publisher}): {src.url}")

        # 이전 초안 + 피드백이 있는 경우
        if version > 1 and review:
            parts.append(f"\n## 이전 초안 (v{version - 1}) 편집 피드백")
            parts.append(f"종합 점수: {review.overall_score}/10")
            if review.strengths:
                parts.append("강점:")
                for s in review.strengths:
                    parts.append(f"  - {s}")

        parts.append(
            "\n---\n"
            "위 브리핑을 바탕으로 1,500~2,500자 분량의 전문적인 블로그 포스트를 "
            "마크다운 형식으로 작성해주세요. "
            "제목은 H1(#)으로, 소제목은 H2(##)로 시작하십시오."
        )

        return "\n".join(parts)

    def _extract_metadata(
        self, markdown: str, brief: ResearchBrief
    ) -> DraftMetadata:
        """생성된 마크다운에서 메타데이터를 추출한다."""
        console.print("  메타데이터 추출 중...", style="dim")

        # 제목 추출 (첫 번째 H1)
        title = brief.topic.title
        for line in markdown.split("\n"):
            if line.startswith("# ") and not line.startswith("## "):
                title = line.lstrip("# ").strip()
                break

        # 글자 수 기반 읽기 시간 추정 (한국어: 분당 약 400자)
        word_count = len(markdown.replace(" ", "").replace("\n", ""))
        read_time = max(1, round(word_count / 400))

        # 간단한 메타데이터 생성
        meta_desc = (
            f"{title} - {brief.topic.angle}"[:155]
        )

        return DraftMetadata(
            title=title,
            meta_description=meta_desc,
            keywords=brief.topic.target_keywords,
            estimated_read_time_minutes=read_time,
        )
