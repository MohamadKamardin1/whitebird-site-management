"""DeepSeek LLM engine.

Wraps the DeepSeek chat-completions API with a clean, production-grade surface:
configuration from settings, an ``enabled`` guard, bounded retries/timeouts,
and error messages that never leak the API key.

Example::

    from apps.integrations import deepseek

    reply = deepseek.complete_chat(
        [{"role": "system", "content": "You are a concise operator."},
         {"role": "user", "content": "Summarise this report: ..."}],
        temperature=0.2,
    )
"""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings

from .transport import ProviderError, request_json

PROVIDER = "DeepSeek"


def enabled() -> bool:
    return bool(settings.DEEPSEEK_ENABLED and settings.DEEPSEEK_API_KEY)


def _require_enabled() -> None:
    if not enabled():
        raise ProviderError(PROVIDER, "DeepSeek integration is not configured.")


def complete_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    """Return the assistant text for a chat conversation."""
    _require_enabled()
    payload: dict[str, Any] = {
        "model": model or settings.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.DEEPSEEK_MAX_TOKENS,
    }
    url = f"{settings.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
    data = request_json(
        provider=PROVIDER,
        method="POST",
        url=url,
        headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=settings.DEEPSEEK_TIMEOUT_SECONDS,
        max_retries=settings.DEEPSEEK_MAX_RETRIES,
    )
    try:
        return cast(str, data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(PROVIDER, "unexpected response shape") from exc


def summarize(text: str, *, instruction: str = "", max_tokens: int | None = None) -> str:
    """Return a concise summary of ``text``.

    ``instruction`` prefixes a system prompt so callers can steer the output.
    """
    if not text.strip():
        raise ProviderError(PROVIDER, "nothing to summarise")
    system = instruction or (
        "You are a concise hospitality operations assistant. "
        "Summarise the input in clear, factual bullet points, no fluff."
    )
    return complete_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": text[:12000]},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
    )
