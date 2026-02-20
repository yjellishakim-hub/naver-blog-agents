from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from blog_agents.agents.base import BaseAgent
from blog_agents.models.content import Draft
from blog_agents.models.research import ResearchBrief
from blog_agents.models.review import EditReview

console = Console()


class EditorAgent(BaseAgent):
    """초안을 6개 차원에서 평가하고 출처 팩트체크를 수행하는 편집장 에이전트."""

    agent_name = "편집장"

    def __init__(self, config):
        model = config.models.get("editor", "claude-sonnet-4-5-20250514")
        super().__init__(config, model=model)
        self.approval_threshold = config.quality.get("approval_threshold", 7.0)

    def review_draft(self, draft: Draft, brief: ResearchBrief) -> EditReview:
        """초안을 검토하고 구조화된 리뷰를 반환한다."""
        console.print(
            f'\n[bold magenta]편집장 에이전트: "{draft.title}" 검토 (v{draft.version})[/]'
        )

        today = datetime.now().strftime("%Y년 %m월 %d일")
        system_prompt = self._load_prompt("editor_agent.md", today=today)
        user_message = self._format_for_review(draft, brief)

        review = self._call_structured(
            system_prompt, user_message, EditReview, max_tokens=4096
        )

        # 메타 정보 설정
        review.draft_id = draft.id
        review.draft_version = draft.version

        # 승인 여부 결정 (threshold 기반)
        review.approved = review.overall_score >= self.approval_threshold

        # 결과 출력
        self._print_review(review)

        return review

    def _format_for_review(self, draft: Draft, brief: ResearchBrief) -> str:
        """초안과 리서치 브리핑을 검토용으로 포맷팅."""
        parts = [
            "# 검토 대상 초안",
            f"제목: {draft.title}",
            f"카테고리: {draft.category.display_name}",
            f"버전: v{draft.version}",
            f"글자 수: {len(draft.full_markdown)}자",
            f"\n## 초안 본문\n{draft.full_markdown}",
            "\n---\n",
            "# 원본 리서치 브리핑 (팩트체크 기준)",
            f"\n## 배경\n{brief.background_context}",
        ]

        if brief.key_facts:
            parts.append("\n## 핵심 팩트 (초안과 교차 검증할 것)")
            for fact in brief.key_facts:
                parts.append(f"- {fact}")

        if brief.exhibition_info:
            parts.append("\n## 전시 기본 정보 (일정·장소·요금 정확성 확인)")
            for info in brief.exhibition_info:
                parts.append(f"- {info}")

        if brief.artist_info:
            parts.append("\n## 작가 정보 (약력·작품세계 정확성 확인)")
            for info in brief.artist_info:
                parts.append(f"- {info}")

        if brief.artwork_highlights:
            parts.append("\n## 주요 작품 (작품명·매체·해석 정확성 확인)")
            for work in brief.artwork_highlights:
                parts.append(f"- {work}")

        if brief.data_points:
            parts.append("\n## 데이터 (수치 정확성 확인)")
            for dp in brief.data_points:
                parts.append(f"- {dp}")

        parts.append(
            f"\n## SEO 키워드\n{', '.join(brief.topic.target_keywords)}"
        )

        # 원본 검색 결과 스니펫 (교차 검증용)
        if brief.raw_source_snippets:
            parts.append("\n---\n")
            parts.append("# 원본 검색 결과 (수집된 원시 데이터)")
            parts.append(
                "아래는 리서치 에이전트가 실제로 수집한 원본 검색 결과입니다.\n"
                "브리핑의 고유명사(작품명, 인물명, 장소명)가 아래 원본 데이터에 "
                "근거하는지 교차 검증하십시오.\n"
                "원본 데이터에 없는 고유명사가 초안에 등장하면 "
                "**사실 정확성 자동 감점** 대상입니다.\n"
            )
            parts.append(brief.raw_source_snippets)

        parts.append(
            "\n---\n"
            "위 초안을 6가지 차원(사실정확성, 문화예술지식, 가독성·문체, SEO, "
            "구성/논리, 실용성/정보가치)으로 평가하고 구체적인 피드백을 제공해주세요.\n\n"
            "**특히 다음 사항을 철저히 검증하세요:**\n"
            "- 작품명, 인물명, 장소명이 원본 검색 결과에 실제로 존재하는지\n"
            "- 전시 일정, 장소, 입장료 등 기본 정보의 정확성\n"
            "- 작가명, 작품명, 용어의 정확성\n"
            "- 독자에게 매력적인 소개와 실용 정보가 있는지\n"
            "- 출처 검증: 각 출처의 실재성과 본문 주장과의 매칭"
        )

        return "\n".join(parts)

    def _print_review(self, review: EditReview):
        """리뷰 결과를 콘솔에 출력."""
        # 점수 테이블
        table = Table(title="편집 평가", show_header=True)
        table.add_column("차원", style="cyan", width=20)
        table.add_column("점수", justify="center", width=8)
        table.add_column("피드백", width=50)

        for dim in review.dimensions:
            score_style = (
                "green" if dim.score >= 8.5
                else "yellow" if dim.score >= 7.0
                else "red"
            )
            table.add_row(
                dim.dimension,
                f"[{score_style}]{dim.score:.1f}[/]",
                dim.feedback[:50] + ("..." if len(dim.feedback) > 50 else ""),
            )

        console.print(table)

        # 종합 결과
        status = (
            "[green bold]승인[/]" if review.approved
            else "[yellow bold]수정 필요[/]"
        )
        console.print(
            f"\n  종합 점수: [bold]{review.overall_score:.1f}[/]/10  |  "
            f"결과: {status}"
        )

        # 강점
        if review.strengths:
            console.print("\n  강점:", style="green")
            for s in review.strengths:
                console.print(f"    + {s}", style="green")

        # 수정 요청
        if not review.approved and review.revision_instructions:
            console.print("\n  수정 요청:", style="yellow")
            for line in review.revision_instructions.split("\n"):
                if line.strip():
                    console.print(f"    > {line.strip()}", style="yellow")
