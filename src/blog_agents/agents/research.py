from __future__ import annotations

import json
import re
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
from blog_agents.tools.web_scraper import ExhibitionScraper

console = Console()


class ResearchAgent(BaseAgent):
    """미술관·갤러리·전시 정보를 수집하고 리서치 브리핑을 생성하는 에이전트."""

    agent_name = "리서치"

    def __init__(self, config):
        model = config.models.get("research", "claude-haiku-4-5-20250514")
        super().__init__(config, model=model)
        self.rss_reader = RSSReader(config.sources)
        self.scraper = ExhibitionScraper()
        self.searcher = WebSearcher()

    def discover_topics(self, category: ContentCategory) -> list[TopicSuggestion]:
        """카테고리별 최신 전시 정보를 수집하고 블로그 토픽을 제안한다."""
        console.print(f"\n[bold blue]리서치 에이전트: {category.display_name} 토픽 탐색[/]")

        mapping = self.config.sources.get("category_source_mapping", {}).get(
            category.value, {}
        )

        rss_items, scraped_items, search_results = self._collect_exhibition_data(
            category, mapping
        )

        # 수집 데이터를 Claude에게 전달하여 토픽 제안
        raw_data = self._format_raw_data(
            rss_items, scraped_items, search_results, category
        )

        today = datetime.now().strftime("%Y년 %m월 %d일")
        system_prompt = self._load_prompt(
            "research_agent.md", category=category.value, today=today
        )

        user_message = (
            f"오늘 날짜: {today}\n\n"
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

        # 토픽 제목 검증: raw_data에 없는 고유명사가 제목에 포함되면 제거
        result.topics = self._validate_topic_titles(result.topics, raw_data)

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
        today = datetime.now().strftime("%Y년 %m월 %d일")
        system_prompt = self._load_prompt(
            "research_agent.md", category=category.value, today=today
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
            f"위 정보를 바탕으로 블로그 작성을 위한 **완벽한** 리서치 브리핑을 작성해주세요.\n\n"
            f"**필수 요구사항:**\n"
            f"- background_context: 3문단 이상 (전시 배경 + 작가/미술사적 맥락 + 시의성)\n"
            f"- key_facts: 최소 7개, 각각 구체적 정보와 (출처명) 포함\n"
            f"- exhibition_info: 전시명, 장소, 기간, 입장료, 운영시간 등 기본 정보\n"
            f"- artist_info: 작가 약력, 작품세계, 흥미로운 뒷이야기\n"
            f"- artwork_highlights: 주요 작품명, 매체, 해석, 숨겨진 이야기\n"
            f"- data_points: 관람객 수, 작품 수 등 수치 정보\n"
            f"- expert_opinions: 큐레이터/평론가 의견, 리뷰\n"
            f"- related_topics: 3~5개\n\n"
            f"작가는 이 브리핑만으로 글을 씁니다. 브리핑에 없는 내용은 쓸 수 없으니 풍부하게 작성하세요.\n"
            f"수집된 자료에 없는 사실을 지어내지 마십시오."
        )

        brief_output = self._call_structured(
            system_prompt, user_message, ResearchBriefOutput
        )

        # 할루시네이션 검증: 브리핑의 고유명사가 원본 자료에 존재하는지 확인
        console.print("  브리핑 팩트 검증 중...", style="dim")
        valid_urls = {r.url for r in deep_results}
        brief_output = self._validate_brief(brief_output, deep_results, topic)
        self._validate_urls(brief_output, valid_urls)
        self._detect_date_repetition(brief_output.key_facts)

        # 미래 날짜 사후 검증 및 제거
        brief_output.key_facts = self._sanitize_future_dates(brief_output.key_facts)
        brief_output.data_points = self._sanitize_future_dates(brief_output.data_points)
        brief_output.expert_opinions = self._sanitize_future_dates(brief_output.expert_opinions)

        # ResearchBrief 조립
        brief = ResearchBrief(
            category=category,
            topic=topic,
            sources=sources,
            background_context=self._remove_future_dates_from_text(brief_output.background_context),
            key_facts=brief_output.key_facts,
            exhibition_info=brief_output.exhibition_info,
            artist_info=brief_output.artist_info,
            artwork_highlights=brief_output.artwork_highlights,
            expert_opinions=brief_output.expert_opinions,
            data_points=brief_output.data_points,
            related_topics=brief_output.related_topics,
            raw_source_snippets=search_context,
        )

        console.print(
            f"  [green]리서치 브리핑 완료 "
            f"(팩트 {len(brief.key_facts)}개, "
            f"전시정보 {len(brief.exhibition_info)}개, "
            f"작품 {len(brief.artwork_highlights)}개)[/]"
        )
        return brief

    def _collect_exhibition_data(self, category, mapping):
        """전시 관련 데이터 수집."""
        # 1. RSS 피드 수집
        console.print("  RSS 피드 수집 중...", style="dim")
        rss_urls = self.rss_reader.get_urls_for_category(category.value)
        rss_items = self.rss_reader.fetch_feeds(rss_urls, days_back=14)

        # 2. 미술관/박물관 전시 목록 스크래핑
        console.print("  전시 목록 확인 중...", style="dim")
        scraped_items = []
        scrape_config = self.config.sources.get("exhibition_scrape", {})
        for institution in mapping.get("institutions", []):
            if institution in scrape_config:
                items = self.scraper.scrape_exhibitions(institution)
                scraped_items.extend(items)

        # 3. 키워드 기반 뉴스 검색
        console.print("  전시 뉴스 검색 중...", style="dim")
        keywords = mapping.get("search_keywords", [])
        search_results = []
        for kw in keywords[:3]:
            results = self.searcher.search_news(f"{kw} 2026", max_results=3)
            search_results.extend(results)

        return rss_items, scraped_items, search_results

    def _format_raw_data(
        self, rss_items, scraped_items, search_results, category
    ) -> str:
        """수집 데이터를 텍스트로 포맷팅."""
        parts = []

        if rss_items:
            parts.append("### RSS 피드 (최근 전시 뉴스)")
            for item in rss_items[:30]:
                date_str = (
                    item.published.strftime("%m/%d") if item.published else "?"
                )
                parts.append(
                    f"- [{date_str}] {item.title} ({item.source})"
                )
                if item.summary:
                    parts.append(f"  요약: {item.summary[:500]}")

        if scraped_items:
            parts.append("\n### 미술관/갤러리 전시 목록")
            for item in scraped_items[:15]:
                parts.append(
                    f"- [{item.date or '?'}] {item.title} ({item.source})"
                )

        if search_results:
            parts.append("\n### 전시 뉴스 검색 결과")
            for item in search_results[:15]:
                parts.append(f"- {item.title}")
                if item.snippet:
                    parts.append(f"  {item.snippet[:500]}")

        parts.append(f"\n### 카테고리: {category.display_name}")
        mapping = self.config.sources.get("category_source_mapping", {}).get(
            category.value, {}
        )
        keywords = mapping.get("search_keywords", [])
        parts.append(f"주요 키워드: {', '.join(keywords)}")

        total = len(rss_items) + len(scraped_items) + len(search_results)
        parts.append(f"\n총 수집 자료: {total}건")

        return "\n".join(parts)

    @staticmethod
    def _sanitize_future_dates(items: list[str]) -> list[str]:
        """리스트의 각 항목에서 미래 날짜를 제거한다."""
        today = datetime.now()
        sanitized = []
        for item in items:
            sanitized.append(ResearchAgent._remove_future_dates_from_text(item))
        return sanitized

    @staticmethod
    def _remove_future_dates_from_text(text: str) -> str:
        """텍스트에서 미래 날짜를 매체명만 남기고 제거한다.

        예: "(한국경제, 2026.2.23)" → "(한국경제)"
            "(2026.2.23)" → ""
        """
        today = datetime.now()

        def check_and_replace(match):
            full = match.group(0)
            year = int(match.group("year"))
            month = int(match.group("month"))
            day = int(match.group("day"))
            try:
                date = datetime(year, month, day)
                if date.date() > today.date():
                    # 미래 날짜 → 날짜 부분만 제거
                    # 앞에 매체명이 있으면 매체명만 남기기
                    prefix = match.group("prefix")
                    if prefix:
                        return f"({prefix.rstrip(', ')})"
                    return ""
            except ValueError:
                pass
            return full

        # 패턴: (매체명, YYYY.M.DD) 또는 (YYYY.M.DD)
        pattern = re.compile(
            r"\((?P<prefix>[^()]*?,\s*)?(?P<year>20\d{2})\.(?P<month>\d{1,2})\.(?P<day>\d{1,2})\)"
        )
        return pattern.sub(check_and_replace, text)

    # ------------------------------------------------------------------
    # 할루시네이션 검증 메서드
    # ------------------------------------------------------------------

    def _validate_topic_titles(
        self,
        topics: list[TopicSuggestion],
        raw_data: str,
    ) -> list[TopicSuggestion]:
        """토픽 제목에 수집 데이터에 없는 고유명사가 포함되면 제목을 정제한다.

        Gemini가 토픽 제안 시 영화 제목 등을 날조하는 패턴을 방지한다.
        예: 자료에 "넘버원"만 있는데 "넘버원 리미니트 밥상"으로 변형.
        """
        corpus_lower = raw_data.lower()

        for topic in topics:
            # 제목에서 따옴표로 감싼 고유명사 추출
            quoted = self.extract_proper_nouns(topic.title)
            for noun in quoted:
                # 원본 데이터에 존재하면 OK
                if noun.lower() in corpus_lower:
                    continue
                # 부분 매칭: 고유명사의 핵심 단어가 corpus에 있는지
                words = noun.split()
                if len(words) <= 1:
                    continue
                # 각 단어 중 corpus에 있는 것만 남겨서 복원
                found_words = [w for w in words if w.lower() in corpus_lower]
                if found_words and len(found_words) < len(words):
                    original = noun
                    corrected = " ".join(found_words)
                    topic.title = topic.title.replace(original, corrected)
                    console.print(
                        f"  [yellow]토픽 제목 정정: '{original}' → "
                        f"'{corrected}'[/]"
                    )

        return topics

    @staticmethod
    def extract_proper_nouns(text: str) -> set[str]:
        """텍스트에서 따옴표/괄호로 감싼 고유명사를 추출한다.

        '...', "...", 《...》, 「...」 패턴을 인식한다.
        2글자 미만 결과는 제외한다.
        """
        patterns = [
            r"['\u2018\u2019]([^'\u2018\u2019]+?)['\u2018\u2019]",
            r"\u201c([^\u201d]+?)\u201d",
            r"《([^》]+?)》",
            r"「([^」]+?)」",
        ]
        terms = set()
        for pat in patterns:
            terms.update(re.findall(pat, text))
        return {t.strip() for t in terms if len(t.strip()) >= 2}

    def _validate_brief(
        self,
        brief_output: ResearchBriefOutput,
        deep_results: list,
        topic: TopicSuggestion,
    ) -> ResearchBriefOutput:
        """브리핑의 고유명사가 원본 검색 결과에 존재하는지 검증한다.

        원본에 없는 고유명사를 포함한 항목은 제거하고 경고를 출력한다.
        """
        # 원본 자료 코퍼스 구성
        source_corpus = " ".join(
            f"{r.title} {r.snippet}" for r in deep_results
        ).lower()

        # 브리핑 전체 텍스트에서 고유명사 추출
        all_brief_text = "\n".join(
            [brief_output.background_context]
            + brief_output.key_facts
            + brief_output.exhibition_info
            + brief_output.artist_info
            + brief_output.artwork_highlights
        )
        proper_nouns = self.extract_proper_nouns(all_brief_text)

        if not proper_nouns:
            return brief_output

        # 각 고유명사가 원본에 존재하는지 확인
        ungrounded = []
        for noun in proper_nouns:
            if noun.lower() not in source_corpus:
                ungrounded.append(noun)

        if not ungrounded:
            console.print("  [green]고유명사 검증 통과[/]")
            return brief_output

        console.print(
            f"  [yellow]검증 경고: 원본 자료에 없는 고유명사 "
            f"{len(ungrounded)}개 발견[/]"
        )
        for term in ungrounded:
            console.print(f"    - '{term}'", style="yellow")

        # 불일치 고유명사를 포함한 항목 제거
        for field_name in [
            "key_facts", "artist_info", "artwork_highlights", "exhibition_info",
        ]:
            items = getattr(brief_output, field_name)
            filtered = [
                item for item in items
                if not any(term in item for term in ungrounded)
            ]
            removed = len(items) - len(filtered)
            if removed > 0:
                console.print(
                    f"    {field_name}: {removed}개 항목 제거",
                    style="yellow",
                )
                setattr(brief_output, field_name, filtered)

        # 핵심 팩트가 너무 적어지면 경고
        if len(brief_output.key_facts) < 3:
            console.print(
                "  [red]경고: 검증 후 핵심 팩트가 3개 미만입니다. "
                "브리핑 신뢰도가 낮을 수 있습니다.[/]"
            )

        return brief_output

    def _validate_urls(
        self, brief_output: ResearchBriefOutput, valid_urls: set[str]
    ) -> None:
        """브리핑 텍스트 내 URL이 실제 수집된 URL인지 확인하고 가짜 URL을 제거한다."""
        url_pattern = re.compile(r"https?://[^\s),\]]+")

        def replace_invalid(match: re.Match) -> str:
            url = match.group(0).rstrip(")")
            # 수집된 URL 중 하나와 prefix가 일치하면 유효
            if any(
                url.startswith(v) or v.startswith(url) for v in valid_urls
            ):
                return match.group(0)
            console.print(
                f"    [yellow]가짜 URL 제거: {url[:80]}[/]"
            )
            return ""

        for field_name in ["expert_opinions", "key_facts"]:
            items = getattr(brief_output, field_name)
            cleaned = [url_pattern.sub(replace_invalid, item) for item in items]
            setattr(brief_output, field_name, cleaned)

        brief_output.background_context = url_pattern.sub(
            replace_invalid, brief_output.background_context
        )

    @staticmethod
    def _detect_date_repetition(
        items: list[str], threshold: int = 4
    ) -> set[str]:
        """동일 날짜가 과도하게 반복되는 패턴을 감지한다.

        반복 날짜가 오늘 날짜와 같으면 날조 가능성이 높으므로 해당 날짜를 제거한다.
        """
        date_pattern = re.compile(r"\d{4}\.\d{1,2}\.\d{1,2}")
        date_counts: dict[str, int] = {}
        for item in items:
            for d in date_pattern.findall(item):
                date_counts[d] = date_counts.get(d, 0) + 1

        suspicious = {d for d, c in date_counts.items() if c >= threshold}
        if not suspicious:
            return set()

        today_str = datetime.now().strftime("%Y.%-m.%-d")
        today_str2 = datetime.now().strftime("%Y.%m.%d")

        for d in suspicious:
            is_today = d in (today_str, today_str2)
            label = " (오늘 날짜 — 날조 가능성 높음)" if is_today else ""
            console.print(
                f"  [yellow]날짜 반복 경고: {d} "
                f"({date_counts[d]}회 반복){label}[/]"
            )

        return suspicious

    def cleanup(self):
        """리소스 정리."""
        self.rss_reader.close()
        self.scraper.close()
        self.searcher.close()
