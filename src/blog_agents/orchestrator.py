from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt

from blog_agents.agents.editor import EditorAgent
from blog_agents.agents.research import ResearchAgent
from blog_agents.agents.writer import WriterAgent
from blog_agents.models.config import AppConfig
from blog_agents.models.content import BlogPost, Draft
from blog_agents.models.research import ContentCategory, ResearchBrief, TopicSuggestion
from blog_agents.models.review import EditReview
from blog_agents.utils.storage import StorageManager, slugify

console = Console()


ROTATION_ORDER = [
    ContentCategory.SEOUL_EXHIBITION,
    ContentCategory.GWANGJU_CULTURE,
    ContentCategory.K_CONTENT,
]


class BlogOrchestrator:
    """리서치 → 작성 → 편집 파이프라인을 관리하는 오케스트레이터."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.research_agent = ResearchAgent(config)
        self.writer_agent = WriterAgent(config)
        self.editor_agent = EditorAgent(config)
        self.storage = StorageManager(config.output_dir)
        self.max_rounds = config.quality.get("max_revision_rounds", 3)

    @property
    def _rotation_state_path(self) -> Path:
        return self.config.root / "config" / "rotation_state.json"

    def get_next_category(self) -> ContentCategory:
        """발행 이력을 확인해서 다음 로테이션 카테고리를 반환.

        1순위: config/rotation_state.json (GitHub Actions 등 CI 환경에서도 동작)
        2순위: output/published/ 파일명에서 추출 (로컬 환경)
        """
        last_category = None

        # 1순위: 상태 파일에서 읽기
        if self._rotation_state_path.exists():
            try:
                state = json.loads(
                    self._rotation_state_path.read_text(encoding="utf-8")
                )
                last_value = state.get("last_category")
                if last_value:
                    last_category = ContentCategory(last_value)
            except (json.JSONDecodeError, ValueError):
                pass

        # 2순위: 로컬 published 파일에서 추출
        if last_category is None:
            published_files = self.storage.list_files("published", "*.md")
            if published_files:
                name = published_files[0].name
                for cat in ContentCategory:
                    if f"_{cat.value}_" in name:
                        last_category = cat
                        break

        if last_category is None:
            return ROTATION_ORDER[0]

        # 다음 카테고리로 이동
        try:
            idx = ROTATION_ORDER.index(last_category)
            next_idx = (idx + 1) % len(ROTATION_ORDER)
        except ValueError:
            next_idx = 0

        return ROTATION_ORDER[next_idx]

    def _save_rotation_state(self, category: ContentCategory) -> None:
        """현재 사용된 카테고리를 상태 파일에 저장."""
        state = {
            "last_category": category.value,
            "last_generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self._rotation_state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run_full_pipeline(
        self,
        category: ContentCategory,
        auto_select: bool = False,
    ) -> BlogPost | None:
        """전체 파이프라인을 실행: 리서치 → 토픽 선택 → 작성 → 편집 → 발행."""

        console.print(
            Panel(
                f"[bold]블로그 에이전트 파이프라인 시작[/]\n"
                f"카테고리: {category.display_name}",
                style="blue",
            )
        )

        # ===== PHASE 1: 리서치 =====
        console.print(
            Panel("Phase 1: 리서치 - 이슈 수집 및 토픽 제안", style="blue")
        )
        topics = self.research_agent.discover_topics(category)

        if not topics:
            console.print("[red]토픽을 찾지 못했습니다.[/]")
            return None

        # 토픽 선택
        if auto_select:
            selected_topic = topics[0]
            console.print(
                f'  자동 선택: "{selected_topic.title}"', style="dim"
            )
        else:
            selected_topic = self._user_select_topic(topics)

        # 리서치 브리핑 생성
        brief = self.research_agent.build_brief(selected_topic, category)
        brief_path = self.storage.save_json(
            "research", brief, category, selected_topic.title, "_brief"
        )
        console.print(f"  리서치 브리핑 저장: {brief_path.name}", style="dim")

        # ===== PHASE 2: 작성 & 편집 루프 =====
        console.print(
            Panel("Phase 2: 작성 & 편집 - 피드백 루프", style="green")
        )

        result = self.run_write_edit_loop(brief, category)
        if result is None:
            return None

        draft, review = result

        # ===== PHASE 3: 최종 발행 =====
        console.print(Panel("Phase 3: 최종 발행", style="cyan"))

        blog_post = BlogPost(
            draft=draft,
            final_score=review.overall_score,
            editor_notes=(
                "; ".join(review.strengths) if review.strengths else ""
            ),
        )

        # 최종 마크다운 저장
        final_path = self.storage.save_markdown(
            "published",
            draft.full_markdown,
            category,
            draft.title,
            "_final",
            frontmatter=blog_post.frontmatter,
        )

        # 로테이션 상태 저장
        self._save_rotation_state(category)

        console.print(
            Panel(
                f"[bold green]파이프라인 완료![/]\n\n"
                f"제목: {draft.title}\n"
                f"최종 점수: {review.overall_score:.1f}/10\n"
                f"수정 라운드: {draft.version}회\n"
                f"저장 위치: {final_path}",
                style="green",
            )
        )

        return blog_post

    def run_write_edit_loop(
        self,
        brief: ResearchBrief,
        category: ContentCategory,
    ) -> tuple[Draft, EditReview] | None:
        """작가 ↔ 편집장 피드백 루프를 실행."""

        # 초안 작성
        draft = self.writer_agent.write_draft(brief, version=1)
        self.storage.save_markdown(
            "drafts", draft.full_markdown, category, draft.title, "_v1"
        )

        best_draft = draft
        best_review: EditReview | None = None
        best_score = 0.0

        for round_num in range(1, self.max_rounds + 1):
            console.print(
                f"\n[bold]--- 편집 라운드 {round_num}/{self.max_rounds} ---[/]"
            )

            # 편집장 검토
            review = self.editor_agent.review_draft(draft, brief)
            self.storage.save_json(
                "reviews", review, category, draft.title,
                f"_review_v{draft.version}",
            )

            # 최고 점수 추적
            if review.overall_score > best_score:
                best_score = review.overall_score
                best_draft = draft
                best_review = review

            # 승인된 경우
            if review.approved:
                console.print(
                    f"\n[green bold]v{draft.version} 승인! "
                    f"(점수: {review.overall_score:.1f})[/]"
                )
                return draft, review

            # 마지막 라운드인 경우
            if round_num == self.max_rounds:
                console.print(
                    f"\n[yellow]최대 수정 횟수 도달. "
                    f"최고 점수 버전 사용 (v{best_draft.version}, "
                    f"{best_score:.1f}점)[/]"
                )
                return best_draft, best_review

            # 수정 요청 → 재작성
            console.print(
                f"\n[yellow]수정 요청 (점수: {review.overall_score:.1f})[/]"
            )
            draft = self.writer_agent.write_draft(
                brief, version=round_num + 1, review=review
            )
            self.storage.save_markdown(
                "drafts",
                draft.full_markdown,
                category,
                draft.title,
                f"_v{draft.version}",
            )

        return best_draft, best_review

    def run_research_only(
        self, category: ContentCategory
    ) -> list[TopicSuggestion]:
        """리서치만 실행하고 토픽 제안을 반환."""
        return self.research_agent.discover_topics(category)

    def _user_select_topic(
        self, topics: list[TopicSuggestion]
    ) -> TopicSuggestion:
        """사용자에게 토픽을 선택받는다."""
        console.print("\n[bold]토픽을 선택하세요:[/]\n")

        for i, topic in enumerate(topics, 1):
            console.print(f"  [cyan]{i}.[/] {topic.title}")
            console.print(f"     관점: {topic.angle}", style="dim")
            console.print(f"     시의성: {topic.timeliness}", style="dim")
            console.print(
                f"     키워드: {', '.join(topic.target_keywords)}",
                style="dim",
            )
            console.print(
                f"     관심도: {'★' * round(topic.estimated_interest * 5)}",
                style="yellow",
            )
            console.print()

        choice = IntPrompt.ask(
            "번호 선택", default=1, choices=[str(i) for i in range(1, len(topics) + 1)]
        )
        selected = topics[choice - 1]
        console.print(f'\n  선택: "{selected.title}"', style="bold")
        return selected

    def cleanup(self):
        """리소스 정리."""
        self.research_agent.cleanup()
