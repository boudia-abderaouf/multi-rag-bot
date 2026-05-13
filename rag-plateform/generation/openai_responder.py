from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai_client import build_openai_client


@dataclass
class OpenAIResponder:
    api_key: str
    model: str
    client: Any = None

    def __post_init__(self):
        if self.client is None:
            self.client = build_openai_client(self.api_key)

    @classmethod
    def from_settings(cls, settings) -> "OpenAIResponder":
        return cls(
            api_key=settings.OPENAI_API_KEY,
            model=settings.RESPONSE_MODEL,
        )

    def is_available(self) -> bool:
        return bool(self.api_key and self.model and self.client is not None)

    def answer(self, prompt: str) -> str:
        if not self.is_available():
            raise RuntimeError("Generation OpenAI non configuree ou dependance openai absente.")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        message = response.choices[0].message.content
        if isinstance(message, list):
            return "".join(
                part.get("text", "") for part in message if isinstance(part, dict)
            ).strip()
        return (message or "").strip()
