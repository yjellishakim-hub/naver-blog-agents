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


def _make_naive(dt: datetime) -> datetime:
    """timezone-aware datetime을 naive로 변환 (UTC 기준)."""
    if dt.tzinfo is not None:
        dt = dt.utctimetuple()
        return datetime(*dt[:6])
    return dt


def _parse_date(date_str: str | None) -> Optional[datetime]:
    """다양한 한국어 날짜 형식을 파싱. 항상 naive datetime 반환."""
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
            result = datetime.strptime(date_str.strip(), fmt)
            return _make_naive(result)
        except ValueError:
            continue

    return None


class RSSReader:
    """RSS 피드를 읽고 파싱하는 도구."""

    def __init__(self, sources_config: dict):
        self.sources = sources_config
        self.client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "BlogAgents/1.0 (Korean Art Exhibition Blog)"},
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

        for entry in feed.entries[:30]:  # 피드당 최대 30개로 제한 (속도 최적화)
            pub_date = _parse_date(
                entry.get("published") or entry.get("updated")
            )

            # 시간 필터링
            if pub_date and pub_date < cutoff:
                continue

            raw_url = entry.get("link", "")
            # Google News RSS URL은 토픽 제안 시에는 디코딩 생략 (속도 최적화)
            # 실제 출처 URL은 build_brief 단계에서 디코딩함

            items.append(
                RSSItem(
                    title=entry.get("title", "").strip(),
                    url=raw_url,
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

        if category == "k_content":
            # K-콘텐츠는 전용 RSS 사용
            kcontent_rss = self.sources.get("kcontent_rss", {})
            for publisher in kcontent_rss.values():
                for feed_url in publisher.values():
                    if isinstance(feed_url, str):
                        urls.append(feed_url)
        else:
            # 전시 카테고리: 기관 RSS + 미술 매체 RSS
            institution_rss = self.sources.get("institution_rss", {})
            for publisher in institution_rss.values():
                for feed_url in publisher.values():
                    if isinstance(feed_url, str):
                        urls.append(feed_url)

            art_media_rss = self.sources.get("art_media_rss", {})
            for publisher in art_media_rss.values():
                for feed_url in publisher.values():
                    if isinstance(feed_url, str):
                        urls.append(feed_url)

        return urls

    def close(self):
        self.client.close()
