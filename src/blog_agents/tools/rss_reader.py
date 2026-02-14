from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import httpx
from rich.console import Console

console = Console()


@dataclass
class RSSItem:
    title: str
    url: str
    published: Optional[datetime]
    summary: str
    source: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "published": self.published.isoformat() if self.published else None,
            "summary": self.summary[:500],
            "source": self.source,
        }


def _parse_date(date_str: str | None) -> Optional[datetime]:
    """다양한 한국어 날짜 형식을 파싱."""
    if not date_str:
        return None

    # feedparser의 parsed time 사용
    try:
        parsed = feedparser._parse_date(date_str)
        if parsed:
            return datetime(*parsed[:6])
    except Exception:
        pass

    # 한국 정부 사이트에서 자주 쓰는 형식들
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y.%m.%d",
        "%Y.%m.%d %H:%M",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    return None


class RSSReader:
    """RSS 피드를 읽고 파싱하는 도구."""

    def __init__(self, sources_config: dict):
        self.sources = sources_config
        self.client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "BlogAgents/1.0 (Korean Economic/Legal Blog)"},
            follow_redirects=True,
        )

    def fetch_feeds(
        self, urls: list[str], days_back: int = 7
    ) -> list[RSSItem]:
        """여러 RSS URL에서 피드를 가져와 시간순으로 정렬."""
        cutoff = datetime.now() - timedelta(days=days_back)
        all_items: list[RSSItem] = []

        for url in urls:
            try:
                items = self._fetch_single_feed(url, cutoff)
                all_items.extend(items)
                time.sleep(0.5)  # 서버 부하 방지
            except Exception as e:
                console.print(f"  [RSS] {url} 피드 오류: {e}", style="yellow")

        # 시간 역순 정렬 (None은 맨 뒤)
        all_items.sort(
            key=lambda x: x.published or datetime.min, reverse=True
        )
        return all_items

    def _fetch_single_feed(
        self, url: str, cutoff: datetime
    ) -> list[RSSItem]:
        """단일 RSS 피드를 가져와 파싱."""
        response = self.client.get(url)
        response.raise_for_status()

        feed = feedparser.parse(response.text)
        source_name = feed.feed.get("title", "Unknown")
        items: list[RSSItem] = []

        for entry in feed.entries:
            pub_date = _parse_date(
                entry.get("published") or entry.get("updated")
            )

            # 시간 필터링
            if pub_date and pub_date < cutoff:
                continue

            items.append(
                RSSItem(
                    title=entry.get("title", "").strip(),
                    url=entry.get("link", ""),
                    published=pub_date,
                    summary=self._clean_summary(
                        entry.get("summary", entry.get("description", ""))
                    ),
                    source=source_name,
                )
            )

        console.print(
            f"  [RSS] {source_name}: {len(items)}개 항목", style="dim"
        )
        return items

    def _clean_summary(self, text: str) -> str:
        """HTML 태그 제거 및 텍스트 정리."""
        import re

        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:500]

    def get_urls_for_category(self, category: str) -> list[str]:
        """카테고리에 해당하는 RSS URL 목록 반환."""
        urls: list[str] = []
        mapping = self.sources.get("category_source_mapping", {}).get(category, {})
        gov_names = mapping.get("government", [])

        # 정부 RSS
        gov_rss = self.sources.get("government_rss", {})
        for name in gov_names:
            if name in gov_rss:
                for feed_url in gov_rss[name].values():
                    if isinstance(feed_url, str):
                        urls.append(feed_url)

        # 뉴스 RSS (전체 포함)
        news_rss = self.sources.get("news_rss", {})
        for publisher in news_rss.values():
            for feed_url in publisher.values():
                if isinstance(feed_url, str):
                    urls.append(feed_url)

        return urls

    def close(self):
        self.client.close()
