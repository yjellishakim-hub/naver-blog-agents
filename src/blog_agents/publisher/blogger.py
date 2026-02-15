"""Google Blogger API를 통한 글 발행."""
from __future__ import annotations

import json
import re
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
  line-height: 2;
  font-size: 17px;
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
}
.econlaw-post h4 {
  font-size: 17px;
  font-weight: 700;
  color: #4A3F38;
  margin: 24px 0 12px;
}
.econlaw-post p {
  margin-bottom: 20px;
  line-height: 2;
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
  line-height: 1.8;
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
  padding: 6px 0 6px 16px;
  position: relative;
  line-height: 1.5;
}
.econlaw-post .references li::before {
  content: '·';
  position: absolute;
  left: 0;
  color: #D35400;
  font-weight: 900;
}
.econlaw-post .disclaimer {
  margin-top: 40px;
  padding: 20px 24px;
  background: #FFF8E7;
  border: 1px solid #F0E0B8;
  border-radius: 8px;
  font-size: 13px;
  color: #8B7355;
  line-height: 1.6;
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

        if labels is None:
            kw_str = self._extract_frontmatter_field(md_content, "keywords")
            if kw_str:
                labels = [
                    k.strip().strip('"').strip("'")
                    for k in kw_str.strip("[]").split(",")
                ]

        # 마크다운 → HTML → 인라인 CSS 래핑
        html_content = markdown_to_html(md_content)

        # Schema.org JSON-LD 구조화 데이터 생성
        json_ld = self._build_json_ld(title, meta_description, labels or [])

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
    def _build_json_ld(title: str, description: str, labels: list[str]) -> str:
        """Google 검색 최적화를 위한 Schema.org JSON-LD 생성."""
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
        schema = {
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
        json_str = json.dumps(schema, ensure_ascii=False, indent=2)
        return f'<script type="application/ld+json">\n{json_str}\n</script>'

    def update_post(self, post_id: str, html_content: str, title: str | None = None) -> dict:
        """기존 글의 내용을 업데이트한다."""
        body = {"content": html_content}
        if title:
            body["title"] = title

        console.print(f"  Blogger 글 업데이트 중 (ID: {post_id})...", style="dim")

        response = (
            self.service.posts()
            .update(blogId=self.blog_id, postId=post_id, body=body)
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
