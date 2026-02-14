from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
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


class GovernmentScraper:
    """RSS가 없는 정부 사이트의 보도자료를 스크래핑."""

    # 스크래핑 설정
    CONFIGS = {
        "공정거래위원회": {
            "url": "https://www.ftc.go.kr/www/selectReportUserList.do?key=10",
            "list_selector": "table tbody tr",
            "title_selector": "td.tl a, td:nth-child(2) a",
            "date_selector": "td:nth-child(5), td:last-child",
            "base_url": "https://www.ftc.go.kr",
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

    def scrape_press_releases(
        self, agency: str, max_items: int = 15
    ) -> list[ScrapedItem]:
        """정부 기관 보도자료 목록을 스크래핑."""
        if agency not in self.CONFIGS:
            console.print(
                f"  [스크래퍼] {agency}: 스크래핑 설정 없음", style="yellow"
            )
            return []

        config = self.CONFIGS[agency]
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
                if href and not href.startswith("http"):
                    href = config.get("base_url", "") + href

                date_text = date_el.get_text(strip=True) if date_el else None

                items.append(
                    ScrapedItem(
                        title=title,
                        url=href,
                        date=date_text,
                        source=agency,
                    )
                )

            console.print(
                f"  [스크래퍼] {agency}: {len(items)}개 항목", style="dim"
            )

        except Exception as e:
            console.print(
                f"  [스크래퍼] {agency} 스크래핑 오류: {e}", style="yellow"
            )

        time.sleep(1)  # 서버 부하 방지
        return items

    def fetch_article_text(self, url: str) -> str:
        """개별 기사/보도자료의 본문 텍스트를 가져온다."""
        try:
            response = self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            # 일반적인 본문 영역 셀렉터 시도
            content_selectors = [
                "div.board_view_con",
                "div.view_con",
                "div.bbs_detail",
                "div#content",
                "article",
                "div.content",
            ]

            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    text = content.get_text(separator="\n", strip=True)
                    # 불필요한 공백 정리
                    text = re.sub(r"\n{3,}", "\n\n", text)
                    return text[:3000]

            # 셀렉터로 못 찾으면 body 텍스트 반환
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
