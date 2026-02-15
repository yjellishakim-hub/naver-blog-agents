"""Google Blogger API를 통한 글 발행."""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from blog_agents.publisher.auth import get_blogger_service
from blog_agents.publisher.markdown_to_html import markdown_to_html

console = Console()

# 글 본문에 삽입되는 인라인 CSS (어떤 Blogger 테마에서든 전문적으로 보이도록)
POST_INLINE_CSS = """
<style scoped>
/* 경제법률 인사이트 - 포스트 인라인 스타일 */
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');

.econlaw-post {
  font-family: 'Pretendard Variable', 'Noto Sans KR', -apple-system, sans-serif;
  color: #3A3330;
  line-height: 1.9;
  font-size: 17px;
  letter-spacing: -0.2px;
  word-break: keep-all;
  -webkit-font-smoothing: antialiased;
  max-width: 780px;
}
.econlaw-post h2 {
  font-size: 24px;
  font-weight: 700;
  color: #2D2320;
  margin: 48px 0 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid #E5D9CC;
  letter-spacing: -0.3px;
  position: relative;
}
.econlaw-post h2::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 60px;
  height: 2px;
  background: #D35400;
}
.econlaw-post h3 {
  font-size: 20px;
  font-weight: 700;
  color: #4A3F38;
  margin: 36px 0 16px;
  padding-left: 14px;
  border-left: 3px solid #D35400;
  letter-spacing: -0.3px;
}
.econlaw-post h4 {
  font-size: 17px;
  font-weight: 700;
  color: #4A3F38;
  margin: 24px 0 12px;
}
.econlaw-post p {
  margin-bottom: 18px;
  line-height: 1.9;
  letter-spacing: -0.2px;
}
.econlaw-post strong {
  color: #2D2320;
  font-weight: 700;
}
.econlaw-post ul, .econlaw-post ol {
  margin: 16px 0;
  padding-left: 24px;
}
.econlaw-post li {
  margin-bottom: 8px;
  line-height: 1.9;
  letter-spacing: -0.2px;
}
.econlaw-post blockquote {
  margin: 28px 0;
  padding: 24px 28px;
  background: linear-gradient(135deg, #FAF6F1, #F5EDE4);
  border-left: 4px solid #D35400;
  border-right: none;
  border-top: none;
  border-bottom: none;
  border-radius: 0 8px 8px 0;
  font-size: 16px;
  line-height: 1.9;
  letter-spacing: -0.2px;
  color: #6B5D4F;
}
.econlaw-post table {
  width: 100%;
  border-collapse: collapse;
  margin: 24px 0;
  font-size: 15px;
  border: 1px solid #E5D9CC;
  border-radius: 8px;
  overflow: hidden;
}
.econlaw-post thead, .econlaw-post th {
  background: #2D2320;
  color: #fff;
  padding: 14px 18px;
  text-align: left;
  font-weight: 600;
  font-size: 14px;
}
.econlaw-post td {
  padding: 12px 18px;
  border-bottom: 1px solid #E5D9CC;
}
.econlaw-post tbody tr:nth-child(even) { background: #FAF6F1; }
.econlaw-post tbody tr:hover { background: #FFF5EE; }
.econlaw-post hr {
  border: none;
  height: 1px;
  background: #E5D9CC;
  margin: 40px 0;
}
.econlaw-post .references {
  margin-top: 40px;
  padding: 28px;
  background: #FAF6F1;
  border-radius: 8px;
  border: 1px solid #E5D9CC;
}
.econlaw-post .references h4 {
  font-size: 15px;
  font-weight: 700;
  color: #2D2320;
  margin-bottom: 12px;
  border: none;
  padding: 0;
}
.econlaw-post .references ul {
  list-style: none;
  padding: 0;
}
.econlaw-post .references li {
  font-size: 13px;
  color: #8B7D6B;
  padding: 6px 0;
  line-height: 1.5;
}
.econlaw-post .references .ref-dot {
  color: #D35400;
  font-weight: 900;
  margin-right: 6px;
}
.econlaw-post .disclaimer {
  margin-top: 48px;
  padding: 20px 24px;
  background: #F8F9FA;
  border: 1px solid #E2E6ED;
  border-radius: 8px;
  font-size: 12.5px;
  color: #6B7280;
  line-height: 1.7;
  letter-spacing: -0.1px;
}
.econlaw-post .disclaimer-icon {
  font-size: 16px;
  color: #9CA3AF;
  margin-right: 6px;
}
.econlaw-post .toc {
  margin: 24px 0 36px;
  padding: 20px 28px;
  background: #FAF6F1;
  border: 1px solid #E5D9CC;
  border-radius: 8px;
}
.econlaw-post .toc h4 {
  font-size: 15px;
  font-weight: 700;
  color: #2D2320;
  margin: 0 0 12px;
  border: none;
  padding: 0;
}
.econlaw-post .toc ol {
  margin: 0;
  padding-left: 20px;
}
.econlaw-post .toc li {
  margin-bottom: 6px;
  line-height: 1.6;
  font-size: 15px;
}
.econlaw-post .toc a {
  color: #4A3F38;
  border-bottom: none;
}
.econlaw-post .toc a:hover {
  color: #D35400;
  border-bottom: 1px solid #D35400;
}
.econlaw-post a { color: #2D2320; text-decoration: none; border-bottom: 1px solid #D35400; }
.econlaw-post a:hover { color: #D35400; }

@media (max-width: 768px) {
  .econlaw-post { font-size: 16px; line-height: 1.9; }
  .econlaw-post h2 { font-size: 20px; }
  .econlaw-post h3 { font-size: 18px; }
}
</style>
""".strip()


class BloggerPublisher:
    """Google Blogger에 글을 발행하는 퍼블리셔."""

    def __init__(self, credentials_path: str | Path, blog_id: str):
        if not blog_id:
            raise ValueError(
                "Blog ID가 설정되지 않았습니다.\n"
                ".env 파일에 BLOGGER_BLOG_ID=<blog-id> 를 추가하세요.\n"
                "Blog ID 확인: Blogger 대시보드 URL의 blogID 파라미터"
            )
        self.blog_id = blog_id
        self.service = get_blogger_service(credentials_path)

    def publish_markdown_file(
        self,
        markdown_path: str | Path,
        labels: list[str] | None = None,
        is_draft: bool = False,
    ) -> dict:
        """마크다운 파일을 읽어 Blogger에 발행한다."""
        path = Path(markdown_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

        md_content = path.read_text(encoding="utf-8")

        # frontmatter에서 제목, 키워드, meta_description 추출
        title = self._extract_frontmatter_field(md_content, "title")
        if not title:
            h1_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
            title = h1_match.group(1) if h1_match else path.stem

        meta_description = self._extract_frontmatter_field(md_content, "meta_description") or ""

        # 라벨 결정: 전달된 라벨 + frontmatter keywords 병합
        kw_labels = []
        kw_str = self._extract_frontmatter_field(md_content, "keywords")
        if kw_str:
            kw_labels = [
                k.strip().strip('"').strip("'")
                for k in kw_str.strip("[]").split(",")
                if k.strip()
            ]

        if labels is None:
            labels = kw_labels
        else:
            # 기존 라벨에 keywords 추가 (중복 제거)
            for kw in kw_labels:
                if kw not in labels:
                    labels.append(kw)

        # 마크다운 → HTML → 인라인 CSS 래핑
        html_content = markdown_to_html(md_content)

        # Schema.org JSON-LD 구조화 데이터 생성 (FAQ 포함)
        json_ld = self._build_json_ld(title, meta_description, labels or [], html_content)

        styled_content = self._wrap_with_style(html_content, json_ld)

        return self.publish_html(
            title=title,
            html_content=styled_content,
            labels=labels,
            is_draft=is_draft,
        )

    def publish_html(
        self,
        title: str,
        html_content: str,
        labels: list[str] | None = None,
        is_draft: bool = False,
    ) -> dict:
        """HTML 콘텐츠를 Blogger에 발행한다."""
        body = {
            "kind": "blogger#post",
            "blog": {"id": self.blog_id},
            "title": title,
            "content": html_content,
        }

        if labels:
            body["labels"] = labels

        console.print(f'  Blogger 발행 중: "{title}"...', style="dim")

        request = self.service.posts().insert(
            blogId=self.blog_id,
            body=body,
            isDraft=is_draft,
        )
        response = request.execute()

        status = "초안" if is_draft else "발행"
        console.print(
            f'  [green]Blogger {status} 완료![/] URL: {response.get("url", "N/A")}'
        )

        # LIVE 발행 시 검색엔진에 색인 요청
        if not is_draft:
            post_url = response.get("url", "")
            if post_url:
                self._ping_search_engines(post_url)

        return response

    @staticmethod
    def _wrap_with_style(html_content: str, json_ld: str = "") -> str:
        """HTML 콘텐츠를 전문 스타일 CSS + 구조화 데이터와 함께 래핑한다."""
        parts = [POST_INLINE_CSS]
        if json_ld:
            parts.append(json_ld)
        parts.append(f'<div class="econlaw-post">\n{html_content}\n</div>')
        return "\n".join(parts)

    @staticmethod
    def _build_json_ld(title: str, description: str, labels: list[str], html_content: str = "") -> str:
        """Google 검색 최적화를 위한 Schema.org JSON-LD 생성 (Article + FAQPage)."""
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
        schemas = []

        # 1) Article 스키마
        article = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description[:160] if description else title,
            "author": {
                "@type": "Organization",
                "name": "이코노로",
                "url": "https://econlaw-lab.blogspot.com",
            },
            "publisher": {
                "@type": "Organization",
                "name": "이코노로: 법과 숫자, 그 사이 이야기",
            },
            "datePublished": now,
            "dateModified": now,
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": "https://econlaw-lab.blogspot.com",
            },
            "keywords": ", ".join(labels) if labels else "",
            "inLanguage": "ko-KR",
            "articleSection": labels[0] if labels else "경제",
        }
        schemas.append(article)

        # 2) FAQPage 스키마 (FAQ 섹션이 있는 경우)
        faq_pairs = BloggerPublisher._extract_faq_from_html(html_content)
        if faq_pairs:
            faq_schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": q,
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": a,
                        },
                    }
                    for q, a in faq_pairs
                ],
            }
            schemas.append(faq_schema)

        # 3) BreadcrumbList 스키마 (구글 검색 결과에 카테고리 경로 표시)
        category_name = labels[0] if labels else "경제"
        breadcrumb = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "이코노로",
                    "item": "https://econlaw-lab.blogspot.com",
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": category_name,
                    "item": f"https://econlaw-lab.blogspot.com/search/label/{category_name}",
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": title,
                },
            ],
        }
        schemas.append(breadcrumb)

        parts = []
        for schema in schemas:
            json_str = json.dumps(schema, ensure_ascii=False, indent=2)
            parts.append(f'<script type="application/ld+json">\n{json_str}\n</script>')
        return "\n".join(parts)

    @staticmethod
    def _extract_faq_from_html(html_content: str) -> list[tuple[str, str]]:
        """HTML에서 FAQ 질문-답변 쌍을 추출한다."""
        if not html_content:
            return []

        pairs = []
        # H3 태그에서 Q. 로 시작하는 질문과 그 뒤의 <p> 답변 추출
        pattern = re.compile(
            r"<h3>(?:Q\.\s*)?(.+?)</h3>\s*<p>(.*?)</p>",
            re.DOTALL,
        )
        # FAQ 섹션 영역만 추출
        faq_section = re.search(
            r"자주 묻는 질문.*?(?=<div class=\"disclaimer\"|<div class=\"references\"|<hr|$)",
            html_content,
            re.DOTALL,
        )
        if faq_section:
            for match in pattern.finditer(faq_section.group()):
                question = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                answer = re.sub(r"<[^>]+>", "", match.group(2)).strip()
                if question and answer:
                    pairs.append((question, answer))

        return pairs

    def update_post(
        self,
        post_id: str,
        html_content: str | None = None,
        title: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """기존 글의 내용/제목/라벨을 업데이트한다."""
        body = {}
        if html_content is not None:
            body["content"] = html_content
        if title:
            body["title"] = title
        if labels is not None:
            body["labels"] = labels

        if not body:
            return {}

        console.print(f"  Blogger 글 업데이트 중 (ID: {post_id})...", style="dim")

        response = (
            self.service.posts()
            .patch(blogId=self.blog_id, postId=post_id, body=body)
            .execute()
        )

        console.print(
            f'  [green]업데이트 완료![/] URL: {response.get("url", "N/A")}'
        )
        return response

    def restyle_all_posts(self) -> int:
        """기존 모든 글에 인라인 CSS 스타일을 적용한다."""
        posts = self.list_posts(max_results=50)
        updated = 0

        for post in posts:
            content = post.get("content", "")
            # 이미 스타일이 적용된 글은 건너뜀
            if "econlaw-post" in content:
                console.print(f'  스킵 (이미 적용): {post.get("title", "")}', style="dim")
                continue

            styled = self._wrap_with_style(content)
            self.update_post(post["id"], styled)
            updated += 1

        console.print(f"\n  [green]총 {updated}개 글에 스타일 적용 완료![/]")
        return updated

    def list_posts(self, max_results: int = 10) -> list[dict]:
        """블로그의 최근 글 목록을 가져온다."""
        response = (
            self.service.posts()
            .list(blogId=self.blog_id, maxResults=max_results)
            .execute()
        )
        return response.get("items", [])

    def get_blog_info(self) -> dict:
        """블로그 기본 정보를 가져온다."""
        return self.service.blogs().get(blogId=self.blog_id).execute()

    def _ping_search_engines(self, post_url: str):
        """발행 후 구글·네이버에 색인 요청(ping)을 보낸다."""
        blog_url = "https://econlaw-lab.blogspot.com"
        sitemap_url = f"{blog_url}/sitemap.xml"

        ping_targets = [
            # Google Ping
            (
                "Google",
                f"https://www.google.com/ping?sitemap={urllib.parse.quote(sitemap_url, safe='')}",
            ),
            # Google Webmaster Ping (블로그 업데이트 알림)
            (
                "Google Blog",
                f"https://blogsearch.google.com/ping/RPC2",
            ),
            # Naver 웹마스터 Ping
            (
                "Naver",
                f"https://searchadvisor.naver.com/indexnow?url={urllib.parse.quote(post_url, safe='')}",
            ),
            # IndexNow (Bing, Yandex, Naver 등 공동 프로토콜)
            (
                "IndexNow",
                f"https://api.indexnow.org/indexnow?url={urllib.parse.quote(post_url, safe='')}&key=econlaw-lab",
            ),
        ]

        for name, url in ping_targets:
            try:
                req = urllib.request.Request(url, method="GET")
                req.add_header("User-Agent", "EconlawBlogBot/1.0")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    console.print(f"  [{name}] 색인 요청 완료 (HTTP {resp.status})", style="dim")
            except Exception:
                console.print(f"  [{name}] 색인 요청 실패 (무시)", style="dim")

    @staticmethod
    def _extract_frontmatter_field(md_text: str, field: str) -> Optional[str]:
        """마크다운 frontmatter에서 특정 필드 값을 추출."""
        fm_match = re.match(r"^---\n(.*?)\n---", md_text, re.DOTALL)
        if not fm_match:
            return None
        for line in fm_match.group(1).split("\n"):
            if line.startswith(f"{field}:"):
                return line[len(field) + 1:].strip()
        return None
