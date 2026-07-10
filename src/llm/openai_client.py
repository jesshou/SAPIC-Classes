"""OpenAI API wrapper for classification and SAPIC+ rewriting."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _extract_json(text: str) -> Any:
    """Parse JSON from a model response, tolerating markdown fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


class OpenAIClient:
    """Thin wrapper around the OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or None
        self._client = None

        if self.api_key:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                logger.warning(
                    "openai package not installed; LLM features disabled."
                )

    @property
    def is_available(self) -> bool:
        return self._client is not None and bool(self.api_key)

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion and return the assistant text."""
        if not self.is_available:
            raise RuntimeError(
                "OpenAI client is not configured. Set OPENAI_API_KEY "
                "in your environment or .env file."
            )

        assert self._client is not None
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        return content.strip()

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Any:
        """Chat and parse the response as JSON."""
        raw = self.chat(
            system,
            user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            return _extract_json(raw)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM JSON: %s\nRaw: %s", exc, raw[:500])
            raise
