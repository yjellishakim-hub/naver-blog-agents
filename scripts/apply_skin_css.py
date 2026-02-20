"""네이버 블로그 스킨 CSS — 스킨 편집/세부 디자인 페이지 탐색."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright
from rich.console import Console

console = Console()

NAVER_ID = "linsus"
USER_DATA_DIR = Path.home() / ".blog-agents" / "naver-session"
SCREENSHOT_DIR = Path(__file__).parent.parent / "output"


async def main():
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
        locale="ko-KR",
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # 로그인
    console.print("[bold]로그인 확인...[/]")
    await page.goto(f"https://admin.blog.naver.com/{NAVER_ID}")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)
    if "nid.naver.com" in page.url:
        console.print("[yellow]로그인 필요...[/]")
        await page.wait_for_url(lambda u: "nid.naver.com" not in u, timeout=120_000)
        await asyncio.sleep(2)

    # ── 1) SkinEdit.naver ──
    console.print("\n[bold]1) SkinEdit.naver[/]")
    await page.goto(f"https://admin.blog.naver.com/SkinEdit.naver?blogId={NAVER_ID}")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)
    console.print(f"  URL: {page.url}")
    ss = SCREENSHOT_DIR / "explore_skinedit.png"
    await page.screenshot(path=str(ss), full_page=True)
    console.print(f"  스크린샷: {ss}")

    # ── 2) Remocon.naver (세부 디자인 설정) ──
    console.print("\n[bold]2) Remocon.naver (세부 디자인 설정)[/]")
    await page.goto(f"https://admin.blog.naver.com/Remocon.naver?blogId={NAVER_ID}&loadType=admin&Redirect=Remocon")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)
    console.print(f"  URL: {page.url}")
    ss2 = SCREENSHOT_DIR / "explore_remocon.png"
    await page.screenshot(path=str(ss2), full_page=True)
    console.print(f"  스크린샷: {ss2}")

    # Remocon 페이지 내 CSS/스타일 관련 옵션 확인
    remocon_options = await page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('*').forEach(el => {
            const t = (el.innerText || el.textContent || '').trim();
            if (t.length > 2 && t.length < 40 && el.children.length === 0 &&
                (t.includes('CSS') || t.includes('css') || t.includes('스타일') ||
                 t.includes('글꼴') || t.includes('폰트') || t.includes('서체') ||
                 t.includes('색상') || t.includes('본문') || t.includes('글자'))) {
                items.push(t);
            }
        });
        return [...new Set(items)];
    }""")
    console.print(f"  스타일 관련 옵션: {remocon_options}")

    # ── 3) 글·댓글 스타일 ──
    console.print("\n[bold]3) 글·댓글 스타일[/]")
    await page.goto(f"https://admin.blog.naver.com/Remocon.naver?blogId={NAVER_ID}&loadType=admin&Redirect=Remocon&SelectedMenu=post")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)
    console.print(f"  URL: {page.url}")
    ss3 = SCREENSHOT_DIR / "explore_post_style.png"
    await page.screenshot(path=str(ss3), full_page=True)
    console.print(f"  스크린샷: {ss3}")

    # ── 4) ItemFactorySkin.naver ──
    console.print("\n[bold]4) ItemFactorySkin.naver[/]")
    await page.goto(f"https://admin.blog.naver.com/ItemFactorySkin.naver?blogId={NAVER_ID}")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)
    console.print(f"  URL: {page.url}")
    ss4 = SCREENSHOT_DIR / "explore_itemfactoryskin.png"
    await page.screenshot(path=str(ss4), full_page=True)
    console.print(f"  스크린샷: {ss4}")

    # ── 5) 스킨 변경 (linsus/skin/list) ──
    console.print("\n[bold]5) 스킨 변경[/]")
    await page.goto(f"https://admin.blog.naver.com/{NAVER_ID}/skin/list")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)
    console.print(f"  URL: {page.url}")
    ss5 = SCREENSHOT_DIR / "explore_skin_list.png"
    await page.screenshot(path=str(ss5), full_page=True)
    console.print(f"  스크린샷: {ss5}")

    # 프레임 내용도 확인
    for frame in page.frames:
        if frame.url and frame.url != "about:blank" and frame != page.main_frame:
            console.print(f"  frame: {frame.name} → {frame.url[:80]}")

    console.print("\n[dim]10초 대기 후 종료...[/]")
    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


asyncio.run(main())
