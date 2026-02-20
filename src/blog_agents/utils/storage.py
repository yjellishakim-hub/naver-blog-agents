from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from blog_agents.models.research import ContentCategory


def slugify(text: str, max_length: int = 30) -> str:
    """한국어 텍스트를 파일명에 안전한 슬러그로 변환."""
    # 특수문자 제거, 공백을 하이픈으로
    slug = text.replace(" ", "-").replace("/", "-").replace("\\", "-")
    # 파일명에 쓸 수 없는 문자 제거
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_가-힣")
    slug = "".join(c for c in slug if c in safe_chars or "\uac00" <= c <= "\ud7a3")
    return slug[:max_length]


class StorageManager:
    """로컬 파일 시스템에 아티팩트를 저장/로드."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        for sub in ["research", "drafts", "reviews", "published"]:
            (output_dir / sub).mkdir(parents=True, exist_ok=True)

    def save_json(
        self,
        subdir: str,
        data: BaseModel | dict,
        category: ContentCategory,
        slug: str,
        suffix: str = "",
    ) -> Path:
        """Pydantic 모델 또는 dict를 JSON으로 저장."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}_{category.value}_{slugify(slug)}{suffix}.json"
        path = self.output_dir / subdir / filename

        if isinstance(data, BaseModel):
            content = data.model_dump_json(indent=2, ensure_ascii=False)
        else:
            content = json.dumps(data, indent=2, ensure_ascii=False)

        path.write_text(content, encoding="utf-8")
        return path

    def save_markdown(
        self,
        subdir: str,
        content: str,
        category: ContentCategory,
        slug: str,
        suffix: str = "",
        frontmatter: dict[str, Any] | None = None,
    ) -> Path:
        """마크다운 파일 저장 (frontmatter 포함 가능)."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}_{category.value}_{slugify(slug)}{suffix}.md"
        path = self.output_dir / subdir / filename

        text = ""
        if frontmatter:
            text += "---\n"
            for key, value in frontmatter.items():
                if isinstance(value, list):
                    text += f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
                else:
                    text += f"{key}: {value}\n"
            text += "---\n\n"
        text += content

        path.write_text(text, encoding="utf-8")
        return path

    def list_files(self, subdir: str, pattern: str = "*.json") -> list[Path]:
        """특정 디렉토리의 파일 목록 반환."""
        return sorted(
            (self.output_dir / subdir).glob(pattern),
            key=lambda p: p.name,
            reverse=True,
        )

    def load_json(self, path: Path) -> dict:
        """JSON 파일 로드."""
        return json.loads(path.read_text(encoding="utf-8"))
