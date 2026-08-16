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

from constance import config as constance_config
from django.conf import settings

from .transport import ProviderError, request_json

PROVIDER = "DeepSeek"


def _config(name: str, fallback: str) -> str:
    """Resolve a value from settings/env first, then constance runtime config."""
    return fallback or str(getattr(constance_config, name, "") or "")


def _api_key() -> str:
    return settings.DEEPSEEK_API_KEY or str(getattr(constance_config, "DEEPSEEK_API_KEY", "") or "")


def enabled() -> bool:
    """The integration is reachable whenever an API key is configured.

    Keys resolve from the environment (``DEEPSEEK_API_KEY``) or the runtime
    Integration settings (constance ``DEEPSEEK_API_KEY``). A key present in
    either place enables the engine — no separate flag required.
    """
    return bool(_api_key())


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
    resolved_model = model or _config("DEEPSEEK_MODEL", settings.DEEPSEEK_MODEL)
    resolved_base = _config("DEEPSEEK_API_BASE", settings.DEEPSEEK_BASE_URL)
    payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.DEEPSEEK_MAX_TOKENS,
    }
    url = f"{resolved_base.rstrip('/')}/chat/completions"
    data = request_json(
        provider=PROVIDER,
        method="POST",
        url=url,
        headers={"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"},
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
