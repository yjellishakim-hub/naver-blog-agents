from __future__ import annotations

import json
from abc import ABC
from pathlib import Path
from typing import TypeVar

import anthropic
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from rich.console import Console

T = TypeVar("T", bound=BaseModel)
console = Console()


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스. Anthropic Messages API를 래핑한다."""

    agent_name: str = "base"

    def __init__(self, config, model: str | None = None):
        self.config = config
        self.model = model or config.models.get("writer", "claude-sonnet-4-5-20250514")
        self.client = anthropic.Anthropic(api_key=config.settings.anthropic_api_key)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(config.prompts_dir)),
            keep_trailing_newline=True,
        )

    def _load_prompt(self, template_name: str, **kwargs) -> str:
        """Jinja2 템플릿에서 프롬프트를 로드하고 렌더링한다."""
        template = self.jinja_env.get_template(template_name)
        return template.render(**kwargs)

    def _call_structured(
        self,
        system_prompt: str,
        user_message: str,
        output_schema: type[T],
        max_tokens: int = 8192,
    ) -> T:
        """Claude를 호출하여 구조화된 Pydantic 모델을 반환받는다."""
        console.print(
            f"  [{self.agent_name}] Calling {self.model} (structured)...",
            style="dim",
        )

        # JSON schema를 system prompt에 포함하는 방식으로 구조화된 출력을 유도
        schema_json = json.dumps(
            output_schema.model_json_schema(), ensure_ascii=False, indent=2
        )
        full_system = (
            f"{system_prompt}\n\n"
            f"## 출력 형식\n"
            f"반드시 아래 JSON 스키마에 맞는 유효한 JSON만 출력하십시오. "
            f"다른 텍스트는 포함하지 마십시오.\n\n```json\n{schema_json}\n```"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=full_system,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()
        # JSON 블록 추출
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            raw_text = "\n".join(json_lines)

        parsed = json.loads(raw_text)
        return output_schema.model_validate(parsed)

    def _call_text(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
    ) -> str:
        """Claude를 호출하여 자유 형식 텍스트를 반환받는다."""
        console.print(
            f"  [{self.agent_name}] Calling {self.model} (text)...",
            style="dim",
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text
