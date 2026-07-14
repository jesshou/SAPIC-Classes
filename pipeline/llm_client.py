"""Thin wrapper around the OpenAI chat API.

Maintains the conversation across repair rounds so the model sees its own
previous attempt alongside the tamarin error message.
Requires OPENAI_API_KEY in the environment.
"""

from openai import OpenAI

from . import config


class LLMSession:
    def __init__(self, system_prompt: str):
        self.client = OpenAI()
        self.messages = [{"role": "system", "content": system_prompt}]

    def send(self, user_content: str) -> str:
        """Append a user turn, get the assistant reply, and keep both in history."""
        self.messages.append({"role": "user", "content": user_content})
        response = self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=self.messages,
        )
        reply = response.choices[0].message.content or ""
        self.messages.append({"role": "assistant", "content": reply})
        return reply
