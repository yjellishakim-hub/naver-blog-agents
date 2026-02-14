"""마크다운을 Blogger용 HTML로 변환 (경제법률 인사이트 테마 대응)."""
from __future__ import annotations

import re


def markdown_to_html(md_text: str) -> str:
    """마크다운 텍스트를 Blogger용 HTML로 변환한다.

    경제법률 인사이트 테마의 CSS 클래스에 맞춰 변환한다.
    """
    # frontmatter 제거
    md_text = re.sub(r"^---\n.*?\n---\n*", "", md_text, flags=re.DOTALL)

    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    in_ordered_list = False
    in_sub_list = False
    in_blockquote = False
    in_references = False

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
                text = _inline_format(ul_match.group(1))
                html_lines.append(f"  <li>{text}</li>")
                continue

        # 면책 고지
        if "면책 고지" in stripped or "면책고지" in stripped:
            text = _inline_format(stripped.lstrip("*> "))
            html_lines.append(f'<div class="disclaimer"><p>{text}</p></div>')
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
