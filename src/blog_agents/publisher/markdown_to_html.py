"""마크다운을 Blogger용 HTML로 변환 (경제법률 인사이트 테마 대응)."""
from __future__ import annotations

import re


def markdown_to_html(md_text: str) -> str:
    """마크다운 텍스트를 Blogger용 HTML로 변환한다.

    경제법률 인사이트 테마의 CSS 클래스에 맞춰 변환한다.
    """
    # frontmatter 제거
    md_text = re.sub(r"^---\n.*?\n---\n*", "", md_text, flags=re.DOTALL)

    # 목차(TOC) 생성을 위해 H2 헤딩 사전 수집
    toc_items = []
    _skip_headings = {"참고자료", "참고 자료", "출처", "References"}
    for line in md_text.split("\n"):
        h2_match = re.match(r"^##\s+(.+)", line.strip())
        if h2_match:
            heading_text = h2_match.group(1).strip()
            # 마크다운 서식 제거
            clean_text = re.sub(r"\*+", "", heading_text).strip()
            if clean_text in _skip_headings:
                continue
            anchor = re.sub(r"[^\w가-힣]", "-", clean_text).strip("-").lower()
            toc_items.append((clean_text, anchor))

    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    in_ordered_list = False
    in_sub_list = False
    in_blockquote = False
    in_references = False
    toc_inserted = False
    toc_index = 0

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # 빈 줄
        if not stripped:
            if in_sub_list:
                html_lines.append("</ul></li>")
                in_sub_list = False
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_ordered_list:
                html_lines.append("</ol>")
                in_ordered_list = False
            if in_blockquote:
                html_lines.append("</blockquote>")
                in_blockquote = False
            continue

        # 헤딩
        heading_match = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = _inline_format(heading_match.group(2))
            # H1은 제목이므로 생략 (Blogger가 자동 생성)
            if level == 1:
                continue
            # 첫 번째 H2 직전에 목차 삽입
            if level == 2 and not toc_inserted and len(toc_items) >= 3:
                html_lines.append(_build_toc(toc_items))
                toc_inserted = True
            # "참고자료" H2는 references 섹션으로 변환
            clean_heading = re.sub(r"<[^>]+>", "", text).strip()
            if level == 2 and clean_heading in ("참고자료", "참고 자료", "출처", "References"):
                in_references = True
                html_lines.append('<div class="references">')
                html_lines.append("<h4>참고자료</h4>")
                html_lines.append("<ul>")
                continue
            # H2에 앵커 추가 (목차 링크용, Blogger 호환)
            if level == 2 and toc_index < len(toc_items):
                anchor = toc_items[toc_index][1]
                html_lines.append(f'<a name="{anchor}"></a>')
                html_lines.append(f'<h{level} id="{anchor}">{text}</h{level}>')
                toc_index += 1
            else:
                html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # 수평선
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            if in_references:
                html_lines.append("</div>")
                in_references = False
            html_lines.append("<hr/>")
            continue

        # 참고자료 섹션 시작
        ref_match = re.match(r"^\*?\*?\[참고자료\]\*?\*?$", stripped)
        if ref_match:
            in_references = True
            html_lines.append('<div class="references">')
            html_lines.append("<h4>참고자료</h4>")
            html_lines.append("<ul>")
            continue

        # 참고자료 섹션 내 리스트 아이템
        if in_references:
            ul_match = re.match(r"^[-*+]\s+(.*)", stripped)
            if ul_match:
                text = _format_reference(ul_match.group(1))
                html_lines.append(f'  <li><span class="ref-dot">·</span>{text}</li>')
                continue

        # 면책 고지
        if ("면책 고지" in stripped or "면책고지" in stripped
                or "본 글은 정보 제공 목적" in stripped
                or "법률 자문이나 투자 권유가 아닙니다" in stripped):
            text = _inline_format(stripped.lstrip("*> "))
            # 이미 disclaimer div가 열려있으면 추가, 아니면 새로 열기
            if html_lines and '<div class="disclaimer">' in html_lines[-1]:
                # 이전 닫는 태그 제거하고 이어붙이기
                last = html_lines.pop()
                last = last.replace("</div>", "")
                html_lines.append(f'{last}<br/>{text}</div>')
            else:
                html_lines.append(
                    f'<div class="disclaimer">'
                    f'<span class="disclaimer-icon">ⓘ</span>{text}</div>'
                )
            continue

        # 면책 고지 두 번째 줄 (전문가 상담 안내)
        if "전문가와 상담" in stripped or "법률·세무 문제" in stripped:
            text = _inline_format(stripped.lstrip("*> "))
            if html_lines and "disclaimer" in html_lines[-1]:
                last = html_lines.pop()
                last = last.replace("</div>", "")
                html_lines.append(f'{last}<br/>{text}</div>')
            else:
                html_lines.append(
                    f'<div class="disclaimer">'
                    f'<span class="disclaimer-icon">ⓘ</span>{text}</div>'
                )
            continue

        # 순서 있는 리스트
        ol_match = re.match(r"^\d+\.\s+(.*)", stripped)
        if ol_match:
            if not in_ordered_list:
                html_lines.append("<ol>")
                in_ordered_list = True
            text = _inline_format(ol_match.group(1))
            html_lines.append(f"  <li>{text}</li>")
            continue

        # 중첩 리스트 (들여쓰기 4칸 이상)
        ul_match = re.match(r"^[-*+]\s+(.*)", stripped)
        if ul_match and indent >= 4 and in_list:
            if not in_sub_list:
                # 마지막 </li>를 제거하고 중첩 시작
                if html_lines and html_lines[-1].strip().endswith("</li>"):
                    last = html_lines.pop()
                    html_lines.append(last.replace("</li>", ""))
                html_lines.append("<ul>")
                in_sub_list = True
            text = _inline_format(ul_match.group(1))
            html_lines.append(f"    <li>{text}</li>")
            continue

        # 순서 없는 리스트
        if ul_match:
            if in_sub_list:
                html_lines.append("</ul></li>")
                in_sub_list = False
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            text = _inline_format(ul_match.group(1))
            html_lines.append(f"  <li>{text}</li>")
            continue

        # 인용
        if stripped.startswith(">"):
            text = _inline_format(stripped.lstrip("> "))
            if not in_blockquote:
                html_lines.append("<blockquote>")
                in_blockquote = True
            html_lines.append(f"<p>{text}</p>")
            continue

        # 일반 문단
        if in_sub_list:
            html_lines.append("</ul></li>")
            in_sub_list = False
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        if in_ordered_list:
            html_lines.append("</ol>")
            in_ordered_list = False

        text = _inline_format(stripped)
        html_lines.append(f"<p>{text}</p>")

    # 닫지 않은 태그 정리
    if in_sub_list:
        html_lines.append("</ul></li>")
    if in_list:
        html_lines.append("</ul>")
    if in_ordered_list:
        html_lines.append("</ol>")
    if in_blockquote:
        html_lines.append("</blockquote>")
    if in_references:
        html_lines.append("</ul></div>")

    return "\n".join(html_lines)


def _build_toc(items: list[tuple[str, str]]) -> str:
    """H2 헤딩 목록으로부터 목차 HTML을 생성한다."""
    toc_lines = [
        '<nav class="toc">',
        "<h4>목차</h4>",
        "<ol>",
    ]
    for text, anchor in items:
        toc_lines.append(f'  <li><a href="#{anchor}">{text}</a></li>')
    toc_lines.append("</ol>")
    toc_lines.append("</nav>")
    return "\n".join(toc_lines)


def _format_reference(text: str) -> str:
    """참고자료 항목을 하이퍼링크가 포함된 HTML로 변환.

    '제목 - 매체명 (날짜): https://...' → '<a href="url">제목 - 매체명 (날짜)</a>'
    """
    # 패턴: 텍스트: URL
    ref_match = re.match(r"^(.+?):\s*(https?://\S+)\s*$", text)
    if ref_match:
        title = _inline_format(ref_match.group(1).strip())
        url = ref_match.group(2).strip()
        return f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
    # 마크다운 링크 [text](url) 형식도 처리
    return _inline_format(text)


def _inline_format(text: str) -> str:
    """인라인 마크다운 서식을 HTML로 변환."""
    # 볼드+이탤릭
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    # 볼드
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    # 이탤릭
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    # 인라인 코드
    text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)
    # 링크
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', text)
    return text
