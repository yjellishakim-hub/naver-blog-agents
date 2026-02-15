from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()


def _resolve_google_news_url(url: str) -> str:
    """Google News RSS 리다이렉트 URL을 실제 기사 URL로 변환한다.

    news.google.com/rss/articles/... 형태의 URL을 원본 기사 URL로 디코딩.
    디코딩 실패 시 원본 URL을 그대로 반환한다.
    """
    if "news.google.com/rss/articles/" not in url:
        return url

    try:
        from googlenewsdecoder import new_decoderv1

        result = new_decoderv1(url, interval=1)
        if result.get("status"):
            decoded = result["decoded_url"]
            console.print(f"  [URL] 디코딩: {decoded[:80]}...", style="dim")
            return decoded
    except ImportError:
        console.print(
            "  [URL] googlenewsdecoder 미설치 → Google News URL 그대로 사용",
            style="yellow",
        )
    except Exception:
        pass

    return url


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
        }


class WebSearcher:
    """간단한 웹 검색 도구.

    참고: 대규모 운영 시에는 Google Custom Search API나
    SerpAPI 같은 전용 검색 API 사용을 권장합니다.
    이 구현은 MVP용 간단한 검색입니다.
    """

    def __init__(self):
        self.client = httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
            },
            follow_redirects=True,
        )

    def search_news(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """뉴스 검색 결과를 반환.

        실제 운영 시에는 뉴스 API (예: NewsAPI, Google News RSS)를
        사용하는 것이 더 안정적입니다.
        """
        results: list[SearchResult] = []

        # Google News RSS를 활용한 검색
        try:
            rss_url = (
                f"https://news.google.com/rss/search"
                f"?q={query}&hl=ko&gl=KR&ceid=KR:ko"
            )
            response = self.client.get(rss_url)
            response.raise_for_status()

            # RSS XML 파싱
            import feedparser

            feed = feedparser.parse(response.text)
            for entry in feed.entries[:max_results]:
                raw_url = entry.get("link", "")
                actual_url = _resolve_google_news_url(raw_url)

                results.append(
                    SearchResult(
                        title=entry.get("title", "").strip(),
                        url=actual_url,
                        snippet=self._clean_html(
                            entry.get("summary", "")
                        )[:300],
                    )
                )

            console.print(
                f'  [검색] "{query}": {len(results)}개 결과', style="dim"
            )

        except Exception as e:
            console.print(
                f'  [검색] "{query}" 검색 오류: {e}', style="yellow"
            )

        return results

    def _clean_html(self, text: str) -> str:
        """HTML 태그를 제거."""
        clean = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\s+", " ", clean).strip()

    def close(self):
        self.client.close()
