"""Gemini API client — thin wrapper using httpx (no heavy SDK dependency).

Uses Google AI Studio REST API:
  POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent

Env vars:
  GEMINI_API_KEY  — required for live calls
  GEMINI_MODEL    — defaults to gemini-2.0-flash
"""

from __future__ import annotations

import os

import httpx

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiClient:
    """Minimal Gemini generateContent client."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    async def generate(self, prompt: str, *, json_mode: bool = True) -> str:
        """Call Gemini generateContent and return the text response.

        Args:
            prompt: The user prompt.
            json_mode: If True, set responseMimeType to application/json.

        Returns:
            Raw text from the model response.

        Raises:
            GeminiError: On API/network errors.
        """
        url = f"{GEMINI_API_BASE}/models/{self.model}:generateContent?key={self.api_key}"

        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        if json_mode:
            body["generationConfig"] = {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            }
        else:
            body["generationConfig"] = {
                "temperature": 0.2,
            }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=body)
            if resp.status_code != 200:
                raise GeminiError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")
            data = resp.json()

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise GeminiError(f"Unexpected Gemini response structure: {exc}") from exc

        return text


class GeminiError(Exception):
    """Raised when Gemini API call fails."""
