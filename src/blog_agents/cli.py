from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from blog_agents.models.config import AppConfig
from blog_agents.models.research import ContentCategory
from blog_agents.orchestrator import BlogOrchestrator

app = typer.Typer(
    name="blog-agents",
    help="한국 미술 전시 블로그 멀티 에이전트 자동화 시스템",
    no_args_is_help=True,
)
console = Console()

CATEGORY_MAP = {
    "seoul": ContentCategory.SEOUL_EXHIBITION,
    "seoul_exhibition": ContentCategory.SEOUL_EXHIBITION,
    "서울전시": ContentCategory.SEOUL_EXHIBITION,
    "서울": ContentCategory.SEOUL_EXHIBITION,
    "gwangju": ContentCategory.GWANGJU_CULTURE,
    "gwangju_culture": ContentCategory.GWANGJU_CULTURE,
    "광주": ContentCategory.GWANGJU_CULTURE,
    "광주문화": ContentCategory.GWANGJU_CULTURE,
    "film": ContentCategory.FILM_REVIEW,
    "film_review": ContentCategory.FILM_REVIEW,
    "영화": ContentCategory.FILM_REVIEW,
    "영화리뷰": ContentCategory.FILM_REVIEW,
    "weekly": ContentCategory.WEEKLY_PICK,
    "weekly_pick": ContentCategory.WEEKLY_PICK,
    "주간": ContentCategory.WEEKLY_PICK,
    "추천": ContentCategory.WEEKLY_PICK,
}


def _resolve_category(category: str) -> ContentCategory:
    """카테고리 문자열을 enum으로 변환."""
    key = category.lower().strip()
    if key in CATEGORY_MAP:
        return CATEGORY_MAP[key]
    raise typer.BadParameter(
        f"알 수 없는 카테고리: '{category}'. "
        f"사용 가능: museum, gallery, artfair, special"
    )


def _get_config(project_dir: Optional[str] = None) -> AppConfig:
    """프로젝트 설정 로드."""
    root = Path(project_dir) if project_dir else Path(__file__).resolve().parents[2]
    return AppConfig(project_root=root)


@app.command()
def generate(
    category: Optional[str] = typer.Argument(
        None,
        help="콘텐츠 카테고리 (museum, gallery, artfair, special). 미지정 시 자동 로테이션",
    ),
    auto: bool = typer.Option(
        False, "--auto", "-a",
        help="토픽 자동 선택 (사용자 입력 없이 실행)",
    ),
    publish_flag: bool = typer.Option(
        False, "--publish", "-p",
        help="생성 후 네이버 블로그에 자동 발행",
    ),
    draft: bool = typer.Option(
        False, "--draft",
        help="임시저장으로 발행 (--publish와 함께 사용)",
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
        help="프로젝트 루트 디렉토리 (기본: 현재 위치에서 자동 감지)",
    ),
):
    """전체 파이프라인 실행: 리서치 → 작성 → 편집 → 발행"""
    config = _get_config(project_dir)

    # 카테고리 미지정 시 자동 로테이션
    if category:
        cat = _resolve_category(category)
    else:
        orchestrator = BlogOrchestrator(config)
        cat = orchestrator.get_next_category()
        console.print(
            f"[bold cyan]자동 로테이션:[/] 다음 카테고리 → {cat.display_name}",
        )

    # --draft 사용 시 --publish 자동 활성화
    if draft:
        publish_flag = True

    publish_mode = ""
    if publish_flag:
        publish_mode = f"\n발행: 네이버 블로그 ({'임시저장' if draft else '즉시 공개'})"

    console.print(
        Panel(
            f"[bold]미술 전시 블로그 에이전트[/]\n"
            f"카테고리: {cat.display_name}\n"
            f"모드: {'자동' if auto else '수동 (토픽 선택)'}{publish_mode}",
            title="blog-agents generate",
            style="blue",
        )
    )

    orchestrator = BlogOrchestrator(config)
    try:
        result = orchestrator.run_full_pipeline(cat, auto_select=auto)
        if result:
            console.print("\n[bold green]블로그 포스트 생성 완료![/]")

            if publish_flag:
                _auto_publish_naver(config, cat, result, is_draft=draft)
        else:
            console.print("\n[yellow]포스트를 생성하지 못했습니다.[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자에 의해 중단됨[/]")
    finally:
        orchestrator.cleanup()


def _auto_publish_naver(config: AppConfig, category, blog_post, is_draft: bool = False):
    """생성된 글을 네이버 블로그에 자동 발행."""
    naver_id = config.settings.naver_blog_id
    if not naver_id:
        console.print("[yellow]NAVER_BLOG_ID 미설정 → 네이버 발행 건너뜀[/]")
        return

    try:
        from blog_agents.publisher.naver import run_naver_publish
        from blog_agents.utils.storage import StorageManager

        storage = StorageManager(config.output_dir)
        cat_value = category.value if hasattr(category, 'value') else str(category)
        published_files = storage.list_files("published", f"*{cat_value}*.md")
        if not published_files:
            console.print("[yellow]발행할 파일을 찾을 수 없습니다.[/]")
            return

        md_path = published_files[0]
        tags = [category.display_name]

        result = run_naver_publish(
            naver_id, md_path, tags=tags, is_draft=is_draft,
        )

        status = "임시저장" if is_draft else "공개"
        console.print(
            Panel(
                f"[bold green]네이버 블로그 {status} 완료![/]\n\n"
                f"제목: {result.get('title', 'N/A')}\n"
                f"URL: {result.get('url', 'N/A')}\n"
                f"상태: {status}",
                style="green",
            )
        )
    except ImportError:
        console.print(
            "[yellow]네이버 발행 의존성 미설치 → 발행 건너뜀[/]\n"
            "실행: pip install blog-agents[naver] && playwright install chromium"
        )
    except Exception as e:
        console.print(f"[red]네이버 발행 실패: {e}[/]")


@app.command()
def research(
    category: str = typer.Argument(
        ...,
        help="콘텐츠 카테고리 (museum, gallery, artfair, special)",
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
    ),
):
    """리서치만 실행하여 토픽 제안을 확인"""
    cat = _resolve_category(category)
    config = _get_config(project_dir)

    orchestrator = BlogOrchestrator(config)
    try:
        topics = orchestrator.run_research_only(cat)

        if not topics:
            console.print("[yellow]제안할 토픽이 없습니다.[/]")
            return

        console.print(
            Panel(f"[bold]{cat.display_name} 토픽 제안[/]", style="blue")
        )

        for i, topic in enumerate(topics, 1):
            console.print(f"\n[cyan bold]{i}. {topic.title}[/]")
            console.print(f"   관점: {topic.angle}")
            console.print(f"   시의성: {topic.timeliness}")
            console.print(f"   키워드: {', '.join(topic.target_keywords)}")
            console.print(
                f"   관심도: {'★' * round(topic.estimated_interest * 5)}"
                f"{'☆' * (5 - round(topic.estimated_interest * 5))}",
                style="yellow",
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]사용자에 의해 중단됨[/]")
    finally:
        orchestrator.cleanup()


@app.command()
def publish(
    file: Optional[str] = typer.Argument(
        None,
        help="발행할 마크다운 파일 경로 (미지정 시 최신 글 선택)",
    ),
    draft: bool = typer.Option(
        False, "--draft",
        help="임시저장으로 발행 (바로 공개하지 않음)",
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
    ),
):
    """생성된 글을 네이버 블로그에 발행"""
    config = _get_config(project_dir)

    # 발행할 파일 결정
    if file:
        md_path = Path(file)
    else:
        from blog_agents.utils.storage import StorageManager
        storage = StorageManager(config.output_dir)
        published = storage.list_files("published", "*.md")
        if not published:
            console.print("[yellow]발행할 글이 없습니다. 먼저 generate를 실행하세요.[/]")
            raise typer.Exit(1)

        console.print("[bold]발행 가능한 글:[/]\n")
        for i, p in enumerate(published[:5], 1):
            console.print(f"  [cyan]{i}.[/] {p.name}")

        from rich.prompt import IntPrompt
        choice = IntPrompt.ask(
            "\n번호 선택", default=1,
            choices=[str(i) for i in range(1, min(len(published), 5) + 1)]
        )
        md_path = published[choice - 1]

    if not md_path.exists():
        console.print(f"[red]파일을 찾을 수 없습니다: {md_path}[/]")
        raise typer.Exit(1)

    _publish_naver(config, md_path, draft)


def _publish_naver(config: AppConfig, md_path: Path, draft: bool):
    """네이버 블로그에 발행."""
    naver_id = config.settings.naver_blog_id
    if not naver_id:
        console.print(
            "[red]NAVER_BLOG_ID가 설정되지 않았습니다.[/]\n\n"
            "1. .env 파일에 추가: NAVER_BLOG_ID=<네이버아이디>\n"
            "2. 최초 실행 시: blog-agents naver-login"
        )
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold]네이버 블로그 발행[/]\n"
            f"파일: {md_path.name}\n"
            f"모드: {'임시저장' if draft else '즉시 발행'}",
            title="blog-agents publish",
            style="green",
        )
    )

    try:
        from blog_agents.publisher.naver import run_naver_publish

        tags = None
        for cat in ContentCategory:
            if cat.value in md_path.name:
                tags = [cat.display_name]
                break

        result = run_naver_publish(
            naver_id, md_path, tags=tags, is_draft=draft,
        )

        console.print(
            Panel(
                f"[bold green]네이버 발행 완료![/]\n\n"
                f"제목: {result.get('title', 'N/A')}\n"
                f"URL: {result.get('url', 'N/A')}\n"
                f"상태: {'임시저장' if draft else '공개'}",
                style="green",
            )
        )

    except ImportError:
        console.print(
            "[red]네이버 발행 의존성이 설치되지 않았습니다.[/]\n"
            "실행: pip install blog-agents[naver] && playwright install chromium"
        )
        raise typer.Exit(1)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]발행 실패: {e}[/]")
        raise typer.Exit(1)


@app.command()
def status(
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
    ),
):
    """최근 생성된 콘텐츠 현황 확인"""
    config = _get_config(project_dir)
    from blog_agents.utils.storage import StorageManager

    storage = StorageManager(config.output_dir)

    console.print(Panel("[bold]블로그 에이전트 현황[/]", style="blue"))

    # 발행된 글
    published = storage.list_files("published", "*.md")
    table = Table(title="최근 발행 글", show_header=True)
    table.add_column("날짜", width=12)
    table.add_column("파일명", width=50)

    for p in published[:10]:
        date_part = p.name[:10] if len(p.name) > 10 else "-"
        table.add_row(date_part, p.name)

    if published:
        console.print(table)
    else:
        console.print("  아직 발행된 글이 없습니다.", style="dim")

    # 통계
    drafts = storage.list_files("drafts", "*.md")
    reviews = storage.list_files("reviews", "*.json")
    briefs = storage.list_files("research", "*.json")

    console.print(f"\n  리서치 브리핑: {len(briefs)}개")
    console.print(f"  초안: {len(drafts)}개")
    console.print(f"  리뷰: {len(reviews)}개")
    console.print(f"  발행: {len(published)}개")


@app.command()
def naver_login(
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
    ),
):
    """네이버 블로그 로그인 및 세션 저장 (최초 1회)"""
    config = _get_config(project_dir)
    naver_id = config.settings.naver_blog_id
    if not naver_id:
        console.print(
            "[red]NAVER_BLOG_ID가 설정되지 않았습니다.[/]\n"
            ".env 파일에 NAVER_BLOG_ID=<네이버아이디> 를 추가하세요."
        )
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold]네이버 블로그 로그인[/]\n"
            f"블로그 ID: {naver_id}\n\n"
            "브라우저가 열리면 네이버 계정으로 로그인해주세요.\n"
            "로그인 후 세션이 자동 저장되어 이후 발행 시 재로그인이 불필요합니다.",
            title="blog-agents naver-login",
            style="green",
        )
    )

    try:
        from blog_agents.publisher.naver import run_naver_login

        success = run_naver_login(naver_id)
        if success:
            console.print(
                Panel(
                    "[bold green]네이버 로그인 세션 저장 완료![/]\n\n"
                    "이제 다음 명령어로 네이버 블로그에 발행할 수 있습니다:\n"
                    "  blog-agents publish\n"
                    "  blog-agents generate --auto --publish",
                    style="green",
                )
            )
        else:
            console.print("[red]네이버 로그인에 실패했습니다. 다시 시도해주세요.[/]")
            raise typer.Exit(1)
    except ImportError:
        console.print(
            "[red]네이버 발행 의존성이 설치되지 않았습니다.[/]\n"
            "실행: pip install blog-agents[naver] && playwright install chromium"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]로그인 실패: {e}[/]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
