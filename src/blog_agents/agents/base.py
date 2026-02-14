from __future__ import annotations

import json
import time
from abc import ABC
from typing import TypeVar

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from rich.console import Console

T = TypeVar("T", bound=BaseModel)
console = Console()


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스. Google Gemini API (google-genai SDK)."""

    agent_name: str = "base"

    def __init__(self, config, model: str | None = None):
        self.config = config
        self.model = model or config.models.get("writer", "gemini-2.0-flash")
        self.client = genai.Client(api_key=config.settings.gemini_api_key)
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
        max_retries: int = 2,
    ) -> T:
        """Gemini를 호출하여 구조화된 Pydantic 모델을 반환받는다."""
        schema_json = json.dumps(
            output_schema.model_json_schema(), ensure_ascii=False, indent=2
        )
        full_prompt = (
            f"{system_prompt}\n\n"
            f"## 출력 형식\n"
            f"반드시 아래 JSON 스키마에 맞는 유효한 JSON만 출력하십시오. "
            f"다른 텍스트는 포함하지 마십시오.\n\n"
            f"{schema_json}\n\n"
            f"---\n\n"
            f"{user_message}"
        )

        for attempt in range(max_retries + 1):
            console.print(
                f"  [{self.agent_name}] {self.model} 호출 중 (구조화)"
                + (f" 재시도 {attempt}..." if attempt else "..."),
                style="dim",
            )

            response = self._call_with_retry(
                full_prompt,
                max_output_tokens=max_tokens,
                temperature=0.7,
                response_mime_type="application/json",
            )

            raw_text = response.text.strip()

            # JSON 블록이 마크다운으로 감싸진 경우 추출
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

            try:
                parsed = json.loads(raw_text)
                return output_schema.model_validate(parsed)
            except (json.JSONDecodeError, Exception) as e:
                if attempt < max_retries:
                    console.print(
                        f"  [yellow]JSON 파싱 실패, 재시도...[/]",
                    )
                    continue
                # 마지막 시도: 잘린 JSON 복구 시도
                repaired = self._try_repair_json(raw_text)
                if repaired is not None:
                    return output_schema.model_validate(repaired)
                raise

    @staticmethod
    def _try_repair_json(text: str):
        """잘린 JSON을 복구 시도."""
        # 끝에 빠진 괄호/따옴표 보완
        for suffix in ['"}', '"}]', '"}]}', '"}}', '"}]}}', '']:
            try:
                return json.loads(text + suffix)
            except json.JSONDecodeError:
                continue
        # 마지막 완전한 항목까지 잘라서 시도
        for i in range(len(text) - 1, 0, -1):
            if text[i] == '}':
                try:
                    return json.loads(text[:i + 1])
                except json.JSONDecodeError:
                    continue
        return None

    def _call_text(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
    ) -> str:
        """Gemini를 호출하여 자유 형식 텍스트를 반환받는다."""
        console.print(
            f"  [{self.agent_name}] {self.model} 호출 중 (텍스트)...",
            style="dim",
        )

        full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"

        response = self._call_with_retry(
            full_prompt,
            max_output_tokens=max_tokens,
            temperature=0.8,
        )

        return response.text

    def _call_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
        **config_kwargs,
    ):
        """Rate limit 시 자동 재시도."""
        for attempt in range(max_retries):
            try:
                return self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
            except ClientError as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    wait = 30 * (attempt + 1)
                    console.print(
                        f"  [yellow]Rate limit - {wait}초 대기 후 재시도...[/]"
                    )
                    time.sleep(wait)
                else:
                    raise
