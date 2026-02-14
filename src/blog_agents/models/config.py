from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    law_api_key: str = Field(default="", alias="LAW_API_KEY")
    google_credentials_path: str = Field(
        default="config/google/credentials.json",
        alias="GOOGLE_CREDENTIALS_PATH",
    )
    blogger_blog_id: str = Field(default="", alias="BLOGGER_BLOG_ID")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def load_yaml_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class AppConfig:
    """전체 애플리케이션 설정을 관리."""

    def __init__(self, project_root: Optional[Path] = None):
        self.root = project_root or Path(__file__).resolve().parents[3]
        self.settings = Settings(_env_file=str(self.root / ".env"))
        self._yaml = load_yaml_config(self.root / "config" / "settings.yaml")
        self._sources = load_yaml_config(self.root / "config" / "sources.yaml")

    @property
    def models(self) -> dict:
        return self._yaml.get("models", {})

    @property
    def quality(self) -> dict:
        return self._yaml.get("quality", {})

    @property
    def sources(self) -> dict:
        return self._sources

    @property
    def prompts_dir(self) -> Path:
        return self.root / "config" / "prompts"

    @property
    def output_dir(self) -> Path:
        base = self._yaml.get("storage", {}).get("base_path", "./output")
        return self.root / base
