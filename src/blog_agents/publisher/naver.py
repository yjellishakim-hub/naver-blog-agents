"""Playwright 브라우저 자동화를 통한 네이버 블로그 발행."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Optional

from rich.console import Console

from blog_agents.publisher.markdown_to_html import markdown_to_html

console = Console()

# 네이버 블로그 관련 URL
_NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
_NAVER_BLOG_HOME = "https://blog.naver.com"


class NaverBlogPublisher:
    """Playwright 브라우저 자동화로 네이버 블로그에 글을 발행하는 퍼블리셔."""

    def __init__(self, naver_id: str, user_data_dir: Optional[Path] = None):
        if not naver_id:
            raise ValueError(
                "네이버 블로그 ID가 설정되지 않았습니다.\n"
                ".env 파일에 NAVER_BLOG_ID=<네이버아이디> 를 추가하세요."
            )
        self.naver_id = naver_id
        self.user_data_dir = user_data_dir or Path.home() / ".blog-agents" / "naver-session"
        self._context = None
        self._page = None
        self._playwright = None
        self._markdown_dir: Optional[Path] = None

    async def _ensure_browser(self):
        """Playwright persistent browser context를 초기화한다."""
        if self._context is not None:
            return

        from playwright.async_api import async_playwright

        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=False,
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        # 클립보드 읽기/쓰기 권한 부여 (HTML 붙여넣기용)
        await self._context.grant_permissions(
            ["clipboard-read", "clipboard-write"],
            origin="https://blog.naver.com",
        )
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

    async def login(self) -> bool:
        """네이버 로그인 상태를 확인하고, 미로그인 시 수동 로그인을 안내한다."""
        await self._ensure_browser()

        # 로그인 상태 확인: 네이버 블로그 홈에서 로그인 여부 체크
        await self._page.goto(f"{_NAVER_BLOG_HOME}/{self.naver_id}")
        await self._page.wait_for_load_state("networkidle")

        # 글쓰기 버튼이 보이면 로그인된 상태
        write_btn = await self._page.query_selector('a[href*="postwrite"], .buddy_write')
        if write_btn:
            console.print("[green]네이버 로그인 확인 완료![/]")
            return True

        # 미로그인 → 로그인 페이지로 이동
        console.print(
            "\n[bold yellow]네이버 로그인이 필요합니다.[/]\n"
            "브라우저에서 네이버 계정으로 로그인해주세요.\n"
            "로그인 완료 후 자동으로 진행됩니다.\n"
        )
        await self._page.goto(_NAVER_LOGIN_URL)

        # 로그인 완료 대기 (최대 120초)
        try:
            await self._page.wait_for_url(
                lambda url: "nid.naver.com" not in url and "nidlogin" not in url,
                timeout=120_000,
            )
            console.print("[green]네이버 로그인 성공! 세션이 저장되었습니다.[/]")
            return True
        except Exception:
            console.print("[red]로그인 시간 초과 (120초). 다시 시도해주세요.[/]")
            return False

    async def publish_markdown_file(
        self,
        markdown_path: str | Path,
        tags: list[str] | None = None,
        is_draft: bool = False,
        category_name: str | None = None,
    ) -> dict:
        """마크다운 파일을 읽어 네이버 블로그에 발행한다."""
        path = Path(markdown_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

        self._markdown_dir = path.parent
        md_content = path.read_text(encoding="utf-8")

        # frontmatter에서 제목, 키워드 추출
        title = self._extract_frontmatter_field(md_content, "title")
        if not title:
            h1_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
            title = h1_match.group(1) if h1_match else path.stem

        if tags is None:
            kw_str = self._extract_frontmatter_field(md_content, "keywords")
            if kw_str:
                tags = [
                    k.strip().strip('"').strip("'")
                    for k in kw_str.strip("[]").split(",")
                    if k.strip()
                ]

        # 마크다운 → HTML → 네이버 호환 인라인 스타일 적용
        html_content = markdown_to_html(md_content)
        styled_html = self._wrap_for_naver(html_content)

        # 로그인 확인
        logged_in = await self.login()
        if not logged_in:
            raise RuntimeError("네이버 로그인에 실패했습니다.")

        # 글쓰기 페이지 열기
        await self._open_editor()

        # 카테고리 선택
        if category_name:
            await self._select_category(category_name)

        # 제목 입력
        await self._fill_title(title)

        # 본문 입력
        await self._fill_content(styled_html)

        # 발행 또는 임시저장 (태그는 발행 다이얼로그에서 입력)
        result = await self._publish_or_save(is_draft, tags)

        status = "임시저장" if is_draft else "발행"
        console.print(f'[green]네이버 블로그 {status} 완료![/] 제목: "{title}"')

        return {"title": title, "status": status, **result}

    async def _open_editor(self):
        """네이버 블로그 글쓰기 페이지를 연다."""
        editor_url = f"{_NAVER_BLOG_HOME}/{self.naver_id}/postwrite"
        console.print("  글쓰기 페이지 열기...", style="dim")
        await self._page.goto(editor_url)
        await self._page.wait_for_load_state("networkidle")

        # SmartEditor ONE 로드 대기
        await self._page.wait_for_selector(
            '.se-component, .blog_editor',
            timeout=15_000,
        )
        await asyncio.sleep(2)  # 에디터 초기화 대기

        # 임시저장 복구 팝업 등 알림 팝업 처리
        await self._dismiss_popup()

    async def _dismiss_popup(self):
        """에디터 진입 시 나타나는 팝업(임시저장 복구 등)을 닫는다."""
        try:
            popup = await self._page.query_selector('.se-popup-alert-confirm')
            if popup and await popup.is_visible():
                # "아니오" / 취소 버튼 클릭 (새로 작성)
                no_btn = await popup.query_selector(
                    'button.se-popup-button-cancel, button:has-text("아니오")'
                )
                if no_btn:
                    console.print("  팝업 감지 → '아니오' 클릭...", style="dim")
                    await no_btn.click()
                else:
                    # 확인 버튼 클릭 (팝업 닫기)
                    ok_btn = await popup.query_selector(
                        'button.se-popup-button-confirm, button:has-text("확인")'
                    )
                    if ok_btn:
                        console.print("  팝업 감지 → '확인' 클릭...", style="dim")
                        await ok_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass  # 팝업이 없으면 무시

    async def _select_category(self, category_name: str):
        """SmartEditor ONE에서 블로그 카테고리를 선택한다."""
        console.print(f'  카테고리 선택: "{category_name}"', style="dim")

        # 카테고리 버튼 클릭 (여러 셀렉터 시도)
        cat_btn_selectors = [
            'button.se-category-button',
            '.blog_category button',
            '[data-click-area="tpb.category"]',
            'button:has-text("카테고리")',
            '.se-header button:has-text("카테고리")',
        ]

        cat_btn = None
        for sel in cat_btn_selectors:
            try:
                cat_btn = await self._page.query_selector(sel)
                if cat_btn and await cat_btn.is_visible():
                    break
                cat_btn = None
            except Exception:
                cat_btn = None

        if not cat_btn:
            console.print(
                "  [yellow]카테고리 버튼을 찾을 수 없습니다. "
                "카테고리 미설정 상태로 진행합니다.[/]"
            )
            return

        await cat_btn.click()
        await asyncio.sleep(1)

        # 카테고리 목록에서 해당 이름의 항목 클릭
        try:
            cat_item = await self._page.query_selector(
                f'text="{category_name}"'
            )
            if not cat_item:
                # 부분 매칭 시도
                cat_item = await self._page.query_selector(
                    f'li:has-text("{category_name}"), '
                    f'a:has-text("{category_name}"), '
                    f'span:has-text("{category_name}"), '
                    f'button:has-text("{category_name}")'
                )

            if cat_item:
                await cat_item.click()
                await asyncio.sleep(0.5)
                console.print(
                    f'  [green]카테고리 "{category_name}" 선택 완료[/]'
                )
            else:
                console.print(
                    f'  [yellow]카테고리 "{category_name}"을 목록에서 '
                    f'찾을 수 없습니다.[/]'
                )
                # 드롭다운 닫기 (ESC)
                await self._page.keyboard.press("Escape")
        except Exception as e:
            console.print(f"  [yellow]카테고리 선택 실패: {e}[/]")
            await self._page.keyboard.press("Escape")

    async def _fill_title(self, title: str):
        """제목 입력 필드에 제목을 작성한다."""
        console.print("  제목 입력 중...", style="dim")

        import platform as _platform
        select_all_key = "Meta+a" if _platform.system() == "Darwin" else "Control+a"

        # SmartEditor ONE 제목 영역
        el = await self._page.query_selector('.se-title-text .se-text-paragraph')
        if el:
            await el.click()
            await asyncio.sleep(0.3)
            await self._page.keyboard.press(select_all_key)
            await self._page.keyboard.type(title, delay=20)
        else:
            # fallback: Tab으로 이동 후 타이핑
            await self._page.keyboard.type(title, delay=20)

    async def _fill_content(self, html_content: str):
        """SmartEditor ONE에 HTML + 이미지를 삽입한다.

        이미지 마커(<!-- IMG:path|caption -->)가 있으면 세그먼트별로
        텍스트는 클립보드 붙여넣기, 이미지는 SE ONE 업로드로 순차 삽입한다.
        이미지가 없으면 기존처럼 한 번에 붙여넣기한다.
        """
        console.print("  본문 입력 중...", style="dim")

        # 본문 영역 클릭 (커서 위치 설정)
        body_el = await self._page.query_selector('.se-section-text .se-text-paragraph')
        if body_el:
            await body_el.click()
        else:
            await self._page.keyboard.press("Tab")
        await asyncio.sleep(0.5)

        # 이미지 마커 기준으로 세그먼트 분할
        segments = self._split_by_images(html_content)

        # 이미지가 없으면 한 번에 붙여넣기
        if len(segments) == 1 and segments[0]["type"] == "text":
            await self._paste_html(segments[0]["content"])
            console.print("  [dim]클립보드 HTML 붙여넣기 완료[/]")
            return

        # 세그먼트별 순차 삽입
        for i, seg in enumerate(segments):
            if seg["type"] == "text":
                await self._paste_html(seg["content"])
                console.print(f"  [dim]텍스트 세그먼트 {i + 1} 붙여넣기 완료[/]")
            elif seg["type"] == "image":
                console.print(f'  이미지 업로드: {seg["path"]}', style="dim")
                await self._upload_image(seg["path"])
                if seg.get("caption"):
                    caption_html = (
                        f'<p style="font-size:12px; color:#999; margin:10px 0 32px; '
                        f'line-height:1.6;">{seg["caption"]}</p>'
                    )
                    await self._paste_html(caption_html)

        console.print("  [dim]본문 + 이미지 삽입 완료[/]")

    async def _paste_html(self, html: str):
        """클립보드를 통해 HTML을 에디터에 붙여넣는다."""
        import platform as _platform
        modifier = "Meta" if _platform.system() == "Darwin" else "Control"

        await self._page.evaluate(
            """async (html) => {
                const htmlBlob = new Blob([html], { type: 'text/html' });
                const textBlob = new Blob([html], { type: 'text/plain' });
                await navigator.clipboard.write([
                    new ClipboardItem({
                        'text/html': htmlBlob,
                        'text/plain': textBlob,
                    })
                ]);
            }""",
            html,
        )
        await asyncio.sleep(0.3)
        await self._page.keyboard.press(f"{modifier}+v")
        await asyncio.sleep(2)

    async def _upload_image(self, image_path: str):
        """SmartEditor ONE에 이미지를 업로드한다."""
        path = Path(image_path)
        if not path.is_absolute() and self._markdown_dir:
            path = self._markdown_dir / path
        if not path.exists():
            console.print(f"  [yellow]이미지 파일 없음, 건너뜀: {path}[/]")
            return

        console.print(f"  [dim]이미지 업로드 중: {path.name}[/]")

        # SE ONE 이미지 업로드 버튼 찾기 (여러 후보 셀렉터 시도)
        _selectors = [
            'button.se-image-toolbar-button',
            '[data-name="image"]',
            '.se-toolbar-item-image',
            'button[data-click-area="tb.image"]',
            '.se-toolbar button[aria-label*="사진"]',
            '.se-toolbar button[aria-label*="이미지"]',
        ]
        img_btn = None
        for sel in _selectors:
            img_btn = await self._page.query_selector(sel)
            if img_btn:
                break

        if not img_btn:
            console.print("  [red]이미지 업로드 버튼을 찾을 수 없습니다.[/]")
            console.print("  [dim]사용 가능한 툴바 버튼 목록을 출력합니다...[/]")
            buttons = await self._page.evaluate("""() => {
                const btns = document.querySelectorAll('.se-toolbar button');
                return Array.from(btns).map(b => ({
                    class: b.className,
                    ariaLabel: b.getAttribute('aria-label'),
                    dataName: b.getAttribute('data-name'),
                    dataClickArea: b.getAttribute('data-click-area'),
                }));
            }""")
            for b in buttons[:20]:
                console.print(f"    {b}", style="dim")
            return

        # 파일 선택 다이얼로그 처리
        try:
            async with self._page.expect_file_chooser(timeout=5000) as fc_info:
                await img_btn.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(str(path))
            await asyncio.sleep(4)  # 업로드 완료 대기

            # 업로드 후 팝업 처리 (설정 다이얼로그 등)
            await self._dismiss_popup()
            console.print(f"  [green]이미지 업로드 완료: {path.name}[/]")
        except Exception as e:
            console.print(f"  [red]이미지 업로드 실패: {e}[/]")

    async def _fill_tags(self, tags: list[str]):
        """발행 다이얼로그 내 태그 입력 영역에 키워드를 입력한다."""
        console.print(f"  태그 입력 중: {', '.join(tags)}", style="dim")

        # 태그 입력 (#tag-input은 발행 다이얼로그에 있음)
        tag_input = await self._page.query_selector('#tag-input')
        if not tag_input:
            console.print("  [yellow]태그 입력 영역을 찾을 수 없습니다. 건너뜁니다.[/]")
            return

        for tag in tags[:30]:  # 네이버 블로그 태그 최대 30개
            await tag_input.click()
            await tag_input.type(tag.strip(), delay=20)
            await self._page.keyboard.press("Enter")
            await asyncio.sleep(0.3)

    async def _publish_or_save(self, is_draft: bool, tags: list[str] | None = None) -> dict:
        """발행 또는 저장 버튼을 클릭한다."""
        if is_draft:
            # 저장(임시저장) 버튼 클릭
            console.print("  저장 중...", style="dim")
            save_btn = await self._page.query_selector('[data-click-area="tpb.save"]')
            if save_btn:
                await save_btn.click()
                await asyncio.sleep(2)
            return {"action": "draft_saved"}

        else:
            # 발행 버튼 클릭 → 발행 다이얼로그 열기
            console.print("  발행 다이얼로그 열기...", style="dim")
            publish_btn = await self._page.query_selector('[data-click-area="tpb.publish"]')
            if publish_btn:
                await publish_btn.click()
                await asyncio.sleep(2)

            # 다이얼로그에서 태그 입력
            if tags:
                await self._fill_tags(tags)

            # 발행 확인 버튼 클릭 (다이얼로그 하단의 녹색 "발행" 버튼)
            console.print("  발행 확인...", style="dim")
            confirm_btn = await self._page.query_selector('[data-click-area="tpb*i.publish"]')
            if confirm_btn:
                await confirm_btn.click()
            await asyncio.sleep(5)

            # 발행 후 URL 추출
            current_url = self._page.url
            return {"action": "published", "url": current_url}

    @staticmethod
    def _wrap_for_naver(html_content: str) -> str:
        """HTML 콘텐츠를 네이버 SmartEditor ONE 호환 형식으로 변환한다.

        SmartEditor ONE은 붙여넣기 시 대부분의 인라인 스타일을 제거하지만
        <table> 셀의 스타일(border, background-color, padding)은 보존한다.
        디자인 요소를 테이블 기반으로 구현하여 스타일이 유지되도록 한다.
        """
        result = html_content

        # ── 정리 ──
        result = re.sub(r"<!--more-->", "", result)
        result = re.sub(r'<a[^>]*name="[^"]*"[^>]*></a>', "", result)
        result = re.sub(r'<a[^>]*href="#[^"]*"[^>]*>(.*?)</a>', r"\1", result)
        result = re.sub(r"<nav ", "<div ", result)
        result = re.sub(r"</nav>", "</div>", result)
        result = re.sub(r'\s+id="[^"]*"', "", result)

        # ── 1. TOC → 테이블 박스 (리스트 변환 전에 처리) ──
        result = re.sub(
            r'<div class="toc"[^>]*>(.*?)</div>',
            NaverBlogPublisher._toc_to_table,
            result, flags=re.DOTALL,
        )

        # ── 2. References → 테이블 박스 (리스트 변환 전에 처리) ──
        result = re.sub(
            r'<div class="references"[^>]*>(.*?)</div>',
            NaverBlogPublisher._references_to_table,
            result, flags=re.DOTALL,
        )

        # ── 3. 남은 <ol>/<ul> → <p> 텍스트 ──
        result = NaverBlogPublisher._convert_lists_to_paragraphs(result)

        # ── 4. H2 → 테이블 (하단 border) ──
        def _h2(m):
            t = m.group(1).strip()
            return (
                '<table style="width:100%; border-collapse:collapse; '
                'margin:48px 0 24px;"><tr>'
                '<td style="text-align:left; padding:0 0 14px; '
                'border-top:0; border-right:0; border-left:0; '
                'border-bottom:2px solid #1A1A1A;">'
                f'<p style="font-size:22px; color:#1A1A1A; margin:0; '
                f'text-align:left;">'
                f'<b>{t}</b></p></td></tr></table>'
            )
        result = re.sub(r'<h2[^>]*>(.*?)</h2>', _h2, result, flags=re.DOTALL)

        # ── 5. H3 → 테이블 (좌측 border) ──
        def _h3(m):
            t = m.group(1).strip()
            return (
                '<table style="width:100%; border-collapse:collapse; '
                'margin:36px 0 16px;"><tr>'
                '<td style="text-align:left; padding:14px 0 14px 20px; '
                'border-top:0; border-right:0; border-bottom:0; '
                'border-left:3px solid #888;">'
                f'<p style="font-size:18px; color:#1A1A1A; margin:0; '
                f'text-align:left;">'
                f'<b>{t}</b></p></td></tr></table>'
            )
        result = re.sub(r'<h3[^>]*>(.*?)</h3>', _h3, result, flags=re.DOTALL)

        # ── 6. H4 → 볼드 문단 ──
        result = re.sub(
            r'<h4[^>]*>(.*?)</h4>',
            r'<p style="font-size:16px; color:#1A1A1A; margin:24px 0 12px;">'
            r'<b>\1</b></p>',
            result, flags=re.DOTALL,
        )

        # ── 7. Blockquote → 테이블 (좌측 border) ──
        def _bq(m):
            content = m.group(1).strip()
            paras = re.findall(r'<p[^>]*>(.*?)</p>', content, re.DOTALL)
            if not paras:
                paras = [content]
            # 본문 인용과 출처(—로 시작) 분리
            quote_parts = []
            attr_parts = []
            for p in paras:
                p = p.strip()
                if p.startswith("—") or p.startswith("&mdash;"):
                    attr_parts.append(p)
                else:
                    quote_parts.append(p)
            inner_quote = '<br>'.join(quote_parts)
            inner_html = (
                f'<p style="font-size:18px; color:#444; margin:0; '
                f'line-height:1.7;"><i>{inner_quote}</i></p>'
            )
            if attr_parts:
                attr_text = '<br>'.join(attr_parts)
                inner_html += (
                    f'<p style="font-size:13px; color:#999; margin:12px 0 0;">'
                    f'{attr_text}</p>'
                )
            return (
                '<table style="width:100%; border-collapse:collapse; '
                'margin:40px 0;"><tr>'
                '<td style="text-align:left; padding:28px 32px; '
                'border-top:0; border-right:0; border-bottom:0; '
                'border-left:3px solid #1A1A1A;">'
                f'{inner_html}'
                '</td></tr></table>'
            )
        result = re.sub(
            r'<blockquote[^>]*>(.*?)</blockquote>',
            _bq, result, flags=re.DOTALL,
        )

        # ── 8. Disclaimer → 테이블 ──
        def _disclaimer(m):
            content = m.group(1).strip()
            return (
                '<table style="width:100%; border-collapse:collapse; '
                'border:1px solid #EBEBEB; margin:0;"><tr>'
                '<td style="text-align:left; padding:20px 24px; background-color:#FAFAFA;">'
                f'<p style="font-size:12px; color:#AAA; margin:0; '
                f'line-height:1.7;">{content}</p>'
                '</td></tr></table>'
            )
        result = re.sub(
            r'<div class="disclaimer"[^>]*>(.*?)</div>',
            _disclaimer, result, flags=re.DOTALL,
        )

        # ── 9. Section divider → 가운데 정렬 텍스트 ──
        result = re.sub(
            r'<div class="section-divider"[^>]*>(.*?)</div>',
            r'<p style="text-align:center; font-size:13px; color:#D0D0D0; '
            r'margin:56px 0 12px;">\1</p>',
            result, flags=re.DOTALL,
        )

        # ── 10. <hr> → 텍스트 구분선 ──
        result = re.sub(
            r'<hr[^>]*/?>',
            '<p style="text-align:center; color:#E0E0E0; margin:56px 0;">'
            '\u2501' * 28 + '</p>',
            result,
        )

        # ── 11. 일반 <p> 스타일 (style 미적용 태그만) ──
        result = re.sub(
            r'<p(?![^>]*style=)([^>]*)>',
            r'<p style="text-align:left; font-size:16.5px; line-height:2.0; '
            r'color:#333; margin:0 0 22px; word-break:keep-all;"\1>',
            result,
        )

        # ── 12. <strong> → <b>, <em> → <i> (SE ONE 호환) ──
        result = re.sub(r'<strong[^>]*>', '<b>', result)
        result = re.sub(r'</strong>', '</b>', result)
        result = re.sub(r'<em[^>]*>', '<i>', result)
        result = re.sub(r'</em>', '</i>', result)

        # ── 13. <a> 외부 링크 스타일 ──
        result = re.sub(
            r'<a(?![^>]*style=)([^>]*href="https?://[^"]*"[^>]*)>',
            r'<a style="color:#1A1A1A;"\1>',
            result,
        )

        return result

    @staticmethod
    def _toc_to_table(match) -> str:
        """TOC div를 테이블 기반 박스로 변환한다.

        2행 테이블: 1행=타이틀(border-bottom), 2행=목차 항목.
        """
        content = match.group(1)
        items = re.findall(r'<li[^>]*>(.*?)</li>', content, re.DOTALL)

        item_lines = []
        for i, item in enumerate(items, 1):
            item_lines.append(
                f'<p style="margin:8px 0; font-size:14.5px; color:#444; '
                f'line-height:1.9; padding-left:4px;">{i}. {item.strip()}</p>'
            )
        items_html = "\n".join(item_lines)

        return (
            '<table style="width:100%; border-collapse:collapse; '
            'border:1px solid #E5E5E5; margin:0 0 48px;">'
            '<tr><td style="text-align:left; padding:24px 28px 12px; '
            'background-color:#FAFAFA; border-bottom:1px solid #E5E5E5;">'
            '<p style="font-size:11px; color:#1A1A1A; margin:0; '
            'text-align:left;">'
            '<b>CONTENTS</b></p>'
            '</td></tr>'
            '<tr><td style="text-align:left; padding:16px 28px 24px; '
            'background-color:#FAFAFA;">'
            f'{items_html}</td></tr></table>'
        )

    @staticmethod
    def _references_to_table(match) -> str:
        """References div를 테이블 기반 박스로 변환한다."""
        content = match.group(1)
        items = re.findall(r'<li[^>]*>(.*?)</li>', content, re.DOTALL)

        rows = [
            '<p style="font-size:11px; color:#1A1A1A; margin:0 0 14px;">'
            '<b>REFERENCES</b></p>',
        ]
        for item in items:
            rows.append(
                f'<p style="margin:6px 0; font-size:13.5px; color:#666; '
                f'line-height:1.7;">{item.strip()}</p>'
            )

        inner = "\n".join(rows)
        return (
            '<table style="width:100%; border-collapse:collapse; '
            'margin:0 0 40px;"><tr>'
            '<td style="text-align:left; padding:24px 28px; '
            'background-color:#F8F8F8; border-top:2px solid #1A1A1A; '
            'border-right:0; border-bottom:0; border-left:0;">'
            f'{inner}</td></tr></table>'
        )

    @staticmethod
    def _convert_lists_to_paragraphs(html: str) -> str:
        """<ol>/<ul> 리스트를 테이블/텍스트 기반으로 변환한다.

        순서 목록(ol)은 테이블로 변환하여 항목 간 border 구분선을 보존한다.
        """
        import re as _re

        def _replace_ol(match):
            ol_content = match.group(1)
            items = _re.findall(r"<li[^>]*>(.*?)</li>", ol_content, _re.DOTALL)
            rows = []
            for i, item in enumerate(items):
                text = item.strip()
                is_last = i == len(items) - 1
                border = (
                    "border-bottom:1px solid #F0F0F0;"
                    if not is_last else ""
                )
                rows.append(
                    f'<tr><td style="text-align:left; '
                    f'padding:10px 0 10px 4px; {border}">'
                    f'<p style="font-size:15.5px; color:#333; margin:0; '
                    f'line-height:1.8; text-align:left;">'
                    f'<b style="color:#1A1A1A;">{i + 1}.</b>  {text}'
                    f'</p></td></tr>'
                )
            return (
                '<table style="width:100%; border-collapse:collapse; '
                'margin:12px 0;">' + "\n".join(rows) + "</table>"
            )

        def _replace_ul(match):
            ul_content = match.group(1)
            items = _re.findall(r"<li[^>]*>(.*?)</li>", ul_content, _re.DOTALL)
            lines = []
            for item in items:
                text = item.strip()
                lines.append(
                    f'<p style="margin:6px 0; font-size:15.5px; color:#333;">'
                    f'\u2022 {text}</p>'
                )
            return "\n".join(lines)

        result = _re.sub(r"<ol[^>]*>(.*?)</ol>", _replace_ol, html, flags=_re.DOTALL)
        result = _re.sub(r"<ul[^>]*>(.*?)</ul>", _replace_ul, result, flags=_re.DOTALL)
        return result

    async def close(self):
        """브라우저 컨텍스트를 종료한다."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    @staticmethod
    def _split_by_images(html: str) -> list[dict]:
        """HTML을 이미지 마커(<!-- IMG:path|caption -->)로 세그먼트 분할."""
        pattern = r"<!-- IMG:(.*?)\|(.*?) -->"
        segments: list[dict] = []
        last_end = 0
        for m in re.finditer(pattern, html):
            text = html[last_end:m.start()].strip()
            if text:
                segments.append({"type": "text", "content": text})
            segments.append({
                "type": "image",
                "path": m.group(1),
                "caption": m.group(2),
            })
            last_end = m.end()
        text = html[last_end:].strip()
        if text:
            segments.append({"type": "text", "content": text})
        if not segments:
            segments.append({"type": "text", "content": html})
        return segments

    @staticmethod
    def _extract_frontmatter_field(md_text: str, field: str) -> Optional[str]:
        """마크다운 frontmatter에서 특정 필드 값을 추출."""
        fm_match = re.match(r"^---\n(.*?)\n---", md_text, re.DOTALL)
        if not fm_match:
            return None
        for line in fm_match.group(1).split("\n"):
            if line.startswith(f"{field}:"):
                return line[len(field) + 1 :].strip()
        return None


def run_naver_publish(
    naver_id: str,
    markdown_path: str | Path,
    tags: list[str] | None = None,
    is_draft: bool = False,
    category_name: str | None = None,
) -> dict:
    """동기 래퍼: 네이버 블로그에 마크다운 파일을 발행한다."""
    async def _run():
        publisher = NaverBlogPublisher(naver_id)
        try:
            return await publisher.publish_markdown_file(
                markdown_path, tags=tags, is_draft=is_draft,
                category_name=category_name,
            )
        finally:
            await publisher.close()

    return asyncio.run(_run())


def run_naver_login(naver_id: str) -> bool:
    """동기 래퍼: 네이버 로그인을 수행하고 세션을 저장한다."""
    async def _run():
        publisher = NaverBlogPublisher(naver_id)
        try:
            return await publisher.login()
        finally:
            await publisher.close()

    return asyncio.run(_run())
