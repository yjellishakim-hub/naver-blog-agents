from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console

from blog_agents.agents.base import BaseAgent
from blog_agents.models.research import (
    ContentCategory,
    ResearchBrief,
    ResearchBriefOutput,
    Source,
    SourceType,
    TopicSuggestion,
    TopicSuggestionList,
)
from blog_agents.tools.rss_reader import RSSReader
from blog_agents.tools.search import WebSearcher
from blog_agents.tools.web_scraper import GovernmentScraper

console = Console()


class ResearchAgent(BaseAgent):
    """정부부처, 뉴스, 웹에서 이슈를 수집하고 리서치 브리핑을 생성하는 에이전트."""

    agent_name = "리서치"

    def __init__(self, config):
        model = config.models.get("research", "claude-haiku-4-5-20250514")
        super().__init__(config, model=model)
        self.rss_reader = RSSReader(config.sources)
        self.scraper = GovernmentScraper()
        self.searcher = WebSearcher()

    def discover_topics(self, category: ContentCategory) -> list[TopicSuggestion]:
        """카테고리별 최신 이슈를 수집하고 블로그 토픽을 제안한다."""
        console.print(f"\n[bold blue]리서치 에이전트: {category.display_name} 토픽 탐색[/]")

        # 1. RSS 피드 수집
        console.print("  RSS 피드 수집 중...", style="dim")
        rss_urls = self.rss_reader.get_urls_for_category(category.value)
        rss_items = self.rss_reader.fetch_feeds(rss_urls, days_back=7)

        # 2. 정부 보도자료 스크래핑
        console.print("  정부 보도자료 확인 중...", style="dim")
        scraped_items = []
        scrape_config = self.config.sources.get("government_scrape", {})
        mapping = self.config.sources.get("category_source_mapping", {}).get(
            category.value, {}
        )
        for agency in mapping.get("government", []):
            if agency in scrape_config:
                items = self.scraper.scrape_press_releases(agency)
                scraped_items.extend(items)

        # 3. 키워드 기반 뉴스 검색
        console.print("  뉴스 검색 중...", style="dim")
        keywords = mapping.get("news_keywords", [])
        search_results = []
        for kw in keywords[:3]:  # 상위 3개 키워드만
            results = self.searcher.search_news(f"{kw} 2026", max_results=3)
            search_results.extend(results)

        # 4. 수집 데이터를 Claude에게 전달하여 토픽 제안
        raw_data = self._format_raw_data(
            rss_items, scraped_items, search_results, category
        )

        system_prompt = self._load_prompt(
            "research_agent.md", category=category.value
        )

        user_message = (
            f"아래는 최근 {category.display_name} 분야의 수집 데이터입니다.\n"
            f"이 데이터를 분석하여 블로그 포스트로 작성하기 좋은 토픽 3개를 제안해주세요.\n\n"
            f"{raw_data}"
        )

        result = self._call_structured(
            system_prompt, user_message, TopicSuggestionList
        )

        # 카테고리 보정
        for topic in result.topics:
            topic.category = category

        console.print(
            f"  [green]토픽 {len(result.topics)}개 제안 완료[/]"
        )
        return result.topics

    def build_brief(
        self, topic: TopicSuggestion, category: ContentCategory
    ) -> ResearchBrief:
        """선택된 토픽에 대한 상세 리서치 브리핑을 생성한다."""
        console.print(
            f'\n[bold blue]리서치 에이전트: "{topic.title}" 심층 조사[/]'
        )

        # 토픽 관련 추가 검색
        console.print("  심층 검색 중...", style="dim")
        deep_results = self.searcher.search_news(topic.title, max_results=5)
        for kw in topic.target_keywords[:2]:
            more = self.searcher.search_news(kw, max_results=3)
            deep_results.extend(more)

        # 소스 구성
        sources = [
            Source(
                title=r.title,
                url=r.url,
                source_type=SourceType.WEB_SEARCH,
                publisher="검색",
                snippet=r.snippet,
            )
            for r in deep_results
        ]

        # Claude에게 브리핑 작성 요청
        system_prompt = self._load_prompt(
            "research_agent.md", category=category.value
        )

        search_context = "\n".join(
            f"- [{r.title}]({r.url}): {r.snippet}"
            for r in deep_results
        )

        user_message = (
            f"## 선정된 토픽\n"
            f"- 제목: {topic.title}\n"
            f"- 관점: {topic.angle}\n"
            f"- 시의성: {topic.timeliness}\n"
            f"- 키워드: {', '.join(topic.target_keywords)}\n\n"
            f"## 수집된 자료\n{search_context}\n\n"
            f"위 정보를 바탕으로 블로그 작성을 위한 상세 리서치 브리핑을 작성해주세요.\n"
            f"확인되지 않은 내용은 포함하지 마시고, 출처가 명확한 정보만 사용하십시오."
        )

        brief_output = self._call_structured(
            system_prompt, user_message, ResearchBriefOutput
        )

        # ResearchBrief 조립
        brief = ResearchBrief(
            category=category,
            topic=topic,
            sources=sources,
            background_context=brief_output.background_context,
            key_facts=brief_output.key_facts,
            legal_references=brief_output.legal_references,
            expert_opinions=brief_output.expert_opinions,
            data_points=brief_output.data_points,
            related_topics=brief_output.related_topics,
        )

        console.print(
            f"  [green]리서치 브리핑 완료 "
            f"(팩트 {len(brief.key_facts)}개, "
            f"법령 {len(brief.legal_references)}개, "
            f"데이터 {len(brief.data_points)}개)[/]"
        )
        return brief

    def _format_raw_data(
        self, rss_items, scraped_items, search_results, category
    ) -> str:
        """수집 데이터를 텍스트로 포맷팅."""
        parts = []

        if rss_items:
            parts.append("### RSS 피드 (최근 뉴스/보도자료)")
            for item in rss_items[:20]:
                date_str = (
                    item.published.strftime("%m/%d") if item.published else "?"
                )
                parts.append(
                    f"- [{date_str}] {item.title} ({item.source})"
                )
                if item.summary:
                    parts.append(f"  요약: {item.summary[:200]}")

        if scraped_items:
            parts.append("\n### 정부 보도자료")
            for item in scraped_items[:10]:
                parts.append(
                    f"- [{item.date or '?'}] {item.title} ({item.source})"
                )

        if search_results:
            parts.append("\n### 뉴스 검색 결과")
            for item in search_results[:10]:
                parts.append(f"- {item.title}")
                if item.snippet:
                    parts.append(f"  {item.snippet[:200]}")

        parts.append(f"\n### 카테고리: {category.display_name}")
        mapping = self.config.sources.get("category_source_mapping", {}).get(
            category.value, {}
        )
        keywords = mapping.get("news_keywords", [])
        parts.append(f"주요 키워드: {', '.join(keywords)}")

        return "\n".join(parts)

    def cleanup(self):
        """리소스 정리."""
        self.rss_reader.close()
        self.scraper.close()
        self.searcher.close()
