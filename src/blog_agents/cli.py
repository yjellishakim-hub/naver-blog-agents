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
    help="한국 경제·법률 블로그 멀티 에이전트 자동화 시스템",
    no_args_is_help=True,
)
console = Console()

CATEGORY_MAP = {
    "macro": ContentCategory.MACRO_FINANCE,
    "macro_finance": ContentCategory.MACRO_FINANCE,
    "realestate": ContentCategory.REAL_ESTATE_TAX,
    "real_estate_tax": ContentCategory.REAL_ESTATE_TAX,
    "corporate": ContentCategory.CORPORATE_FAIR,
    "corporate_fair": ContentCategory.CORPORATE_FAIR,
    "global": ContentCategory.GLOBAL_NEWS,
    "global_news": ContentCategory.GLOBAL_NEWS,
    "news": ContentCategory.GLOBAL_NEWS,
}


def _resolve_category(category: str) -> ContentCategory:
    """카테고리 문자열을 enum으로 변환."""
    key = category.lower().strip()
    if key in CATEGORY_MAP:
        return CATEGORY_MAP[key]
    raise typer.BadParameter(
        f"알 수 없는 카테고리: '{category}'. "
        f"사용 가능: macro, realestate, corporate, global"
    )


def _get_config(project_dir: Optional[str] = None) -> AppConfig:
    """프로젝트 설정 로드."""
    root = Path(project_dir) if project_dir else Path(__file__).resolve().parents[2]
    return AppConfig(project_root=root)


@app.command()
def generate(
    category: str = typer.Argument(
        ...,
        help="콘텐츠 카테고리 (macro, realestate, corporate)",
    ),
    auto: bool = typer.Option(
        False, "--auto", "-a",
        help="토픽 자동 선택 (사용자 입력 없이 실행)",
    ),
    publish_flag: bool = typer.Option(
        False, "--publish", "-p",
        help="생성 후 Blogger에 자동 발행",
    ),
    draft: bool = typer.Option(
        False, "--draft",
        help="Blogger에 초안으로 발행 (--publish와 함께 사용)",
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
        help="프로젝트 루트 디렉토리 (기본: 현재 위치에서 자동 감지)",
    ),
):
    """전체 파이프라인 실행: 리서치 → 작성 → 편집 → 발행"""
    cat = _resolve_category(category)
    config = _get_config(project_dir)

    # --draft 사용 시 --publish 자동 활성화
    if draft:
        publish_flag = True

    publish_mode = ""
    if publish_flag:
        publish_mode = f"\n발행: {'초안(draft)' if draft else '즉시 공개'}"

    console.print(
        Panel(
            f"[bold]경제·법률 블로그 에이전트[/]\n"
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

            # Blogger 발행
            if publish_flag:
                _auto_publish(config, cat, result, is_draft=draft)
        else:
            console.print("\n[yellow]포스트를 생성하지 못했습니다.[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자에 의해 중단됨[/]")
    finally:
        orchestrator.cleanup()


def _auto_publish(config: AppConfig, category, blog_post, is_draft: bool = False):
    """생성된 글을 Blogger에 자동 발행."""
    blog_id = config.settings.blogger_blog_id
    if not blog_id:
        console.print("[yellow]BLOGGER_BLOG_ID 미설정 → Blogger 발행 건너뜀[/]")
        return

    try:
        from blog_agents.publisher.blogger import BloggerPublisher
        from blog_agents.utils.storage import StorageManager

        credentials_path = config.root / config.settings.google_credentials_path
        publisher = BloggerPublisher(credentials_path, blog_id)

        # 해당 카테고리의 최신 published 파일 찾기
        storage = StorageManager(config.output_dir)
        cat_value = category.value if hasattr(category, 'value') else str(category)
        published_files = storage.list_files("published", f"*{cat_value}*.md")
        if not published_files:
            console.print("[yellow]발행할 파일을 찾을 수 없습니다.[/]")
            return

        md_path = published_files[0]  # 해당 카테고리의 가장 최신 파일

        # 카테고리별 라벨
        labels = None
        yaml_config = config._yaml.get("blogger", {}).get("default_labels", {})
        if cat_value in yaml_config:
            labels = yaml_config[cat_value]

        result = publisher.publish_markdown_file(
            md_path, labels=labels, is_draft=is_draft
        )

        status = "초안" if is_draft else "공개"
        console.print(
            Panel(
                f"[bold green]Blogger {status} 완료![/]\n\n"
                f"제목: {result.get('title', 'N/A')}\n"
                f"URL: {result.get('url', 'N/A')}\n"
                f"상태: {status}",
                style="green",
            )
        )
    except ImportError:
        console.print("[yellow]Blogger 의존성 미설치 → 발행 건너뜀[/]")
    except Exception as e:
        console.print(f"[red]Blogger 발행 실패: {e}[/]")


@app.command()
def research(
    category: str = typer.Argument(
        ...,
        help="콘텐츠 카테고리 (macro, realestate, corporate)",
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
        help="초안으로 발행 (바로 공개하지 않음)",
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
    ),
):
    """생성된 글을 Google Blogger에 발행"""
    config = _get_config(project_dir)

    # Blog ID 확인
    blog_id = config.settings.blogger_blog_id
    if not blog_id:
        console.print(
            "[red]BLOGGER_BLOG_ID가 설정되지 않았습니다.[/]\n\n"
            "1. Blogger(blogger.com)에서 블로그를 생성하세요\n"
            "2. 블로그 대시보드 URL에서 blogID를 복사하세요\n"
            "   예: blogger.com/blog/posts/1234567890\n"
            "3. .env 파일에 추가: BLOGGER_BLOG_ID=1234567890"
        )
        raise typer.Exit(1)

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

        # 최신 파일 표시
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

    console.print(
        Panel(
            f"[bold]Blogger 발행[/]\n"
            f"파일: {md_path.name}\n"
            f"모드: {'초안' if draft else '즉시 발행'}",
            title="blog-agents publish",
            style="blue",
        )
    )

    try:
        from blog_agents.publisher.blogger import BloggerPublisher

        credentials_path = config.root / config.settings.google_credentials_path
        publisher = BloggerPublisher(credentials_path, blog_id)

        # 카테고리별 라벨 추가
        labels = None
        yaml_config = config._yaml.get("blogger", {}).get("default_labels", {})
        for cat_key, cat_labels in yaml_config.items():
            if cat_key in md_path.name:
                labels = cat_labels
                break

        result = publisher.publish_markdown_file(
            md_path, labels=labels, is_draft=draft
        )

        console.print(
            Panel(
                f"[bold green]발행 완료![/]\n\n"
                f"제목: {result.get('title', 'N/A')}\n"
                f"URL: {result.get('url', 'N/A')}\n"
                f"상태: {'초안' if draft else '공개'}",
                style="green",
            )
        )

    except ImportError:
        console.print(
            "[red]Blogger 의존성이 설치되지 않았습니다.[/]\n"
            "실행: pip install blog-agents[publisher]"
        )
        raise typer.Exit(1)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]발행 실패: {e}[/]")
        raise typer.Exit(1)


@app.command()
def fix_labels(
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", "-d",
    ),
):
    """기존 발행 글에 카테고리 라벨을 추가/수정"""
    config = _get_config(project_dir)
    blog_id = config.settings.blogger_blog_id
    if not blog_id:
        console.print("[red]BLOGGER_BLOG_ID가 설정되지 않았습니다.[/]")
        raise typer.Exit(1)

    try:
        from blog_agents.publisher.blogger import BloggerPublisher

        credentials_path = config.root / config.settings.google_credentials_path
        publisher = BloggerPublisher(credentials_path, blog_id)

        posts = publisher.list_posts(max_results=50)
        if not posts:
            console.print("[yellow]발행된 글이 없습니다.[/]")
            return

        yaml_labels = config._yaml.get("blogger", {}).get("default_labels", {})
        updated = 0

        for post in posts:
            post_id = post["id"]
            title = post.get("title", "")
            existing_labels = post.get("labels", [])

            # 카테고리 추정 (제목/라벨 기반)
            new_labels = list(existing_labels)
            for cat_key, cat_labels in yaml_labels.items():
                # 이미 카테고리 라벨이 있으면 건너뜀
                if any(cl in existing_labels for cl in cat_labels):
                    continue
                # 파일명이나 제목에서 카테고리 추정은 어려우므로, 라벨이 없는 글에 기본 라벨 추가
                if not existing_labels:
                    # 제목 키워드로 카테고리 추정
                    macro_kw = ["금리", "경제", "GDP", "인플레", "통화", "연준", "한국은행", "금값", "환율"]
                    realestate_kw = ["부동산", "주택", "세금", "임대", "아파트", "분양", "세법"]
                    corporate_kw = ["기업", "공정거래", "독점", "M&A", "지배구조", "상법"]
                    global_kw = ["글로벌", "미국", "중국", "EU", "국제", "무역"]

                    if any(kw in title for kw in macro_kw):
                        new_labels = yaml_labels.get("macro_finance", [])
                    elif any(kw in title for kw in realestate_kw):
                        new_labels = yaml_labels.get("real_estate_tax", [])
                    elif any(kw in title for kw in corporate_kw):
                        new_labels = yaml_labels.get("corporate_fair", [])
                    elif any(kw in title for kw in global_kw):
                        new_labels = yaml_labels.get("global_news", [])
                    break

            if new_labels and set(new_labels) != set(existing_labels):
                publisher.update_post(post_id, labels=new_labels)
                console.print(f'  [green]라벨 추가:[/] "{title}" → {new_labels}')
                updated += 1
            else:
                console.print(f'  스킵 (이미 라벨 있음): "{title}"', style="dim")

        console.print(f"\n[green]총 {updated}개 글 라벨 업데이트 완료![/]")

    except Exception as e:
        console.print(f"[red]라벨 수정 실패: {e}[/]")
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


if __name__ == "__main__":
    app()
