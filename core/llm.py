"""Тонкий слой доступа к LLM. Без ключа слой просто недоступен —
ассистент падает обратно на детерминированные шаблоны и продолжает работать.

Поддерживаются:
  • OpenAI-совместимый API  (OpenAI, ProxyAPI, OpenRouter, vLLM, локальная модель)
      LLM_API_KEY / OPENAI_API_KEY, LLM_BASE_URL, LLM_MODEL
  • Anthropic
      ANTHROPIC_API_KEY, ANTHROPIC_MODEL
"""
from __future__ import annotations

import os

import requests


class LLMError(RuntimeError):
    pass


def provider() -> str | None:
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None


def model_name() -> str:
    if provider() == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    return os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


def complete(system: str, user: str, timeout: int = 25) -> str:
    kind = provider()
    if kind is None:
        raise LLMError("нет ключа LLM")

    if kind == "anthropic":
        url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1/messages")
        headers = {
            "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model_name(),
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": 500,
            "temperature": 0.2,
        }
    else:
        base = os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        url = f"{base.rstrip('/')}/chat/completions"
        headers = {
            "authorization": f"Bearer {os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY')}",
            "content-type": "application/json",
        }
        payload = {
            "model": model_name(),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": 500,
        }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code >= 400:
        raise LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()

    if kind == "anthropic":
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    return (data["choices"][0]["message"]["content"] or "").strip()
