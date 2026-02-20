from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import httpx
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

        result = new_decoderv1(url, interval=0)
        if result.get("status"):
            decoded = result["decoded_url"]
            return decoded
    except ImportError:
        pass
    except Exception:
        pass

    return url


def _resolve_google_news_urls_batch(urls: list[str], max_workers: int = 10) -> list[str]:
    """여러 Google News URL을 병렬로 디코딩한다."""
    results = list(urls)  # 복사

    # Google News URL만 필터
    indices_to_resolve = [
        i for i, u in enumerate(urls)
        if "news.google.com/rss/articles/" in u
    ]

    if not indices_to_resolve:
        return results

    console.print(
        f"  [URL] {len(indices_to_resolve)}개 Google News URL 병렬 디코딩 중...",
        style="dim",
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_resolve_google_news_url, urls[i]): i
            for i in indices_to_resolve
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                pass  # 실패 시 원본 URL 유지

    decoded_count = sum(
        1 for i in indices_to_resolve if results[i] != urls[i]
    )
    console.print(
        f"  [URL] {decoded_count}/{len(indices_to_resolve)}개 디코딩 완료",
        style="dim",
    )
    return results


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
            entries = feed.entries[:max_results]

            # URL들을 한번에 병렬 디코딩
            raw_urls = [e.get("link", "") for e in entries]
            decoded_urls = _resolve_google_news_urls_batch(raw_urls)

            for entry, actual_url in zip(entries, decoded_urls):
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
