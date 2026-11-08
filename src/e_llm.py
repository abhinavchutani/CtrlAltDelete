"""OpenAI-compatible chat client for the copilot, with an on-disk cache and an offline mode.

Settings from .env: LLM_BASE_URL (e.g. https://api.deepseek.com), LLM_API_KEY, LLM_MODEL.
No key → `available()` is False and the agent uses its deterministic offline stub.
Responses are cached in out/cache/ by a hash of (model, messages, tools), so reruns are reproducible.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.db import REPO_ROOT, env

CACHE_DIR = REPO_ROOT / "out" / "cache" / "llm"


def available() -> bool:
    return bool(env("LLM_API_KEY") and env("LLM_MODEL"))


def model_name() -> str:
    return env("LLM_MODEL", "offline-stub") if available() else "offline-stub"


def _key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


RETRIES = 4
MAX_WAIT_S = 30.0


def _create(client: Any, kwargs: dict) -> Any:
    """chat.completions.create, waiting out short rate limits (free tiers cap tokens per minute)."""
    import re
    import time

    from openai import RateLimitError
    for attempt in range(RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            m = re.search(r"try again in ([\d.]+)\s*(ms|s)", str(e))
            wait = (float(m.group(1)) / (1000 if m.group(2) == "ms" else 1) if m else 2.0 * 2 ** attempt) + 0.5
            if attempt == RETRIES or wait > MAX_WAIT_S:
                raise
            time.sleep(wait)


def _tool_call(t: Any) -> dict:
    """A tool call as a plain dict. Provider extras ride along: Gemini 3 rejects the next turn unless each call's
    `extra_content.google.thought_signature` is sent back unchanged."""
    out = {"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}}
    extra = getattr(t, "extra_content", None) or (getattr(t, "model_extra", None) or {}).get("extra_content")
    if extra:
        out["extra_content"] = extra
    return out


def chat(messages: list[dict], tools: list[dict] | None = None, cache_dir: Path = CACHE_DIR) -> dict:
    """One chat completion → the assistant message as a dict ({content, tool_calls}). Cached."""
    payload = {"model": env("LLM_MODEL"), "messages": messages, "tools": tools or [], "temperature": 0}
    path = cache_dir / f"{_key(payload)}.json"
    if path.exists():
        return json.loads(path.read_text())
    if not available():
        raise RuntimeError("no LLM configured (set LLM_API_KEY and LLM_MODEL in .env)")
    from openai import OpenAI

    client = OpenAI(api_key=env("LLM_API_KEY"), base_url=env("LLM_BASE_URL") or None)
    kwargs: dict[str, Any] = {"model": payload["model"], "messages": messages, "temperature": 0}
    if tools:
        kwargs["tools"] = tools
    msg = _create(client, kwargs).choices[0].message
    out = {"role": "assistant", "content": msg.content or "",
           "tool_calls": [_tool_call(t) for t in (msg.tool_calls or [])]}
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False))
    return out
