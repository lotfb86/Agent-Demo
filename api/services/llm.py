from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from api.services.config import get_settings


@dataclass
class LLMResponse:
    """LLM response with real token usage from OpenRouter."""
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def llm_enabled() -> bool:
    settings = get_settings()
    return bool(settings.use_real_llm and settings.openrouter_api_key)


def _extract_text_from_message(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts).strip()
    return str(content)


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, RuntimeError)),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _chat_completion_request(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 500 or response.status_code in {408, 409, 425, 429}:
        raise RuntimeError(f"OpenRouter temporary error: {response.status_code}")

    if response.status_code >= 400:
        detail = response.text[:300]
        raise RuntimeError(f"OpenRouter request failed ({response.status_code}): {detail}")

    return response.json()


async def llm_chat_with_usage(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 500,
    model: Optional[str] = None,
) -> LLMResponse:
    """Call OpenRouter and return both text and real token usage."""
    settings = get_settings()
    if not llm_enabled():
        raise RuntimeError("Real LLM mode is not enabled")

    payload = {
        "model": model or settings.openrouter_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    data = await _chat_completion_request(payload)
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("OpenRouter response did not contain choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    text = _extract_text_from_message(content).strip()
    if not text:
        raise RuntimeError("OpenRouter response did not contain text content")

    usage = data.get("usage", {})
    return LLMResponse(
        text=text,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )


async def llm_chat(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 500,
    model: Optional[str] = None,
) -> str:
    """Backward-compatible wrapper that returns only the text."""
    response = await llm_chat_with_usage(messages, temperature, max_tokens, model)
    return response.text


def try_parse_json_object(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if not text:
        return None

    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    snippet = text[start : end + 1]
    try:
        value = json.loads(snippet)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        return None

    return None
