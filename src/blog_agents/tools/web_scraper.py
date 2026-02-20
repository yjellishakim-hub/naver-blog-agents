from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()


@dataclass
class ScrapedItem:
    title: str
    url: str
    date: Optional[str]
    source: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "date": self.date,
            "source": self.source,
        }


class ExhibitionScraper:
    """미술관·박물관 사이트에서 전시 목록을 스크래핑."""

    CONFIGS = {
        "국립현대미술관": {
            "url": "https://www.mmca.go.kr/exhibitions/exhibitionList.do",
            "list_selector": "ul.list_exhibition li",
            "title_selector": ".txt_info .tit",
            "date_selector": ".txt_info .date",
            "base_url": "https://www.mmca.go.kr",
        },
        "서울시립미술관": {
            "url": "https://sema.seoul.go.kr/kr/whatson/exhibition/list",
            "list_selector": ".exhibit-list li",
            "title_selector": ".info .tit",
            "date_selector": ".info .date",
            "base_url": "https://sema.seoul.go.kr",
        },
        "국립중앙박물관": {
            "url": "https://www.museum.go.kr/site/main/exhi/special/list",
            "list_selector": ".exhibit_list li",
            "title_selector": ".txt_area .tit",
            "date_selector": ".txt_area .date",
            "base_url": "https://www.museum.go.kr",
        },
    }

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
            follow_redirects=True,
        )

    def scrape_exhibitions(
        self, institution: str, max_items: int = 15
    ) -> list[ScrapedItem]:
        """미술관/박물관 전시 목록을 스크래핑."""
        if institution not in self.CONFIGS:
            console.print(
                f"  [스크래퍼] {institution}: 스크래핑 설정 없음", style="yellow"
            )
            return []

        config = self.CONFIGS[institution]
        items: list[ScrapedItem] = []

        try:
            response = self.client.get(config["url"])
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            rows = soup.select(config["list_selector"])
            for row in rows[:max_items]:
                title_el = row.select_one(config["title_selector"])
                date_el = row.select_one(config["date_selector"])

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                if not href:
                    link_el = row.select_one("a")
                    href = link_el.get("href", "") if link_el else ""
                if href and not href.startswith("http"):
                    href = config.get("base_url", "") + href

                date_text = date_el.get_text(strip=True) if date_el else None

                items.append(
                    ScrapedItem(
                        title=title,
                        url=href,
                        date=date_text,
                        source=institution,
                    )
                )

            console.print(
                f"  [스크래퍼] {institution}: {len(items)}개 전시", style="dim"
            )

        except Exception as e:
            console.print(
                f"  [스크래퍼] {institution} 스크래핑 오류: {e}", style="yellow"
            )

        time.sleep(1)  # 서버 부하 방지
        return items

    def fetch_article_text(self, url: str) -> str:
        """개별 전시 상세 페이지의 본문 텍스트를 가져온다."""
        try:
            response = self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            # 전시 상세 페이지 본문 영역 셀렉터
            content_selectors = [
                "div.exhibit_detail",
                "div.exhibition_view",
                "div.view_con",
                "div.board_view_con",
                "div#content",
                "article",
                "div.content",
            ]

            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    text = content.get_text(separator="\n", strip=True)
                    text = re.sub(r"\n{3,}", "\n\n", text)
                    return text[:3000]

            body = soup.find("body")
            if body:
                return body.get_text(separator="\n", strip=True)[:2000]

        except Exception as e:
            console.print(
                f"  [스크래퍼] 본문 가져오기 실패 ({url}): {e}",
                style="yellow",
            )

        return ""

    def close(self):
        self.client.close()
