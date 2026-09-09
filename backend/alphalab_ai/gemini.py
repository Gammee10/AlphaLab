"""Gemini free-tier provider (docs/ai-assistant.md, ADR 0008/0010).

BYOK via GEMINI_API_KEY; httpx REST (no vendor SDK); structured JSON output;
token budgets + content-hash caching + quota-to-ruled fallback. Transport is
injectable for replay tests (no live key in CI).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

PROVIDER = "gemini"
# Current free-tier GA models (2026-09). gemini-2.5-flash was deprecated for
# new keys (404 "no longer available to new users"); ADR 0010's decision is
# unchanged: Flash default, Pro opt-in for summaries.
MODEL_PROPOSE = "gemini-3.8-flash"
MODEL_SUMMARIZE = "gemini-3.8-flash"
MODEL_SUMMARIZE_PRO = "gemini-pro-latest"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
BUDGETS = {"propose_in": 4000, "propose_out": 2000, "explain_in": 2000, "explain_out": 2000,
           "summarize_in": 8000, "summarize_out": 2000}
ALLOWED_OPS = ("setParam", "addCondition", "removeCondition", "addGroup", "addFilter",
               "removeFilter", "setRisk", "setExits")
TRUNCATION_NOTE = " [truncated for token budget]"


class QuotaExhausted(Exception):
    code = "AI_QUOTA_EXHAUSTED"


class ModelError(Exception):
    code = "AI_VALIDATION_FAILED"


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _truncate(text: str, budget: int) -> tuple[str, bool]:
    if estimate_tokens(text) <= budget:
        return text, False
    chars = budget * 4
    return text[:chars] + TRUNCATION_NOTE, True


_SECRET_PATTERNS = (
    re.compile(r"(?i)(key|token|secret|authorization)\s*=\s*[^\s&;]+"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"x-goog-api-key['\"]?\s*:\s*[^\s\"',}]+", re.IGNORECASE),
)


def redact_secrets(text: str) -> str:
    """Scrub key-like material (docs/security.md redaction promise)."""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted


def _endpoint(model: str) -> str:
    # The API key travels in the x-goog-api-key header, never the URL
    # (URLs land in proxy/HTTP-client logs).
    return f"{API_BASE}/models/{model}:generateContent"


def _headers(key: str) -> dict[str, str]:
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def _generate(request_fn: Callable[..., Any], model: str, key: str, prompt: str,
              out_budget: int, schema: dict[str, Any]) -> tuple[dict[str, Any], int, int]:
    prompt, truncated = _truncate(prompt, BUDGETS["propose_in"])
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2, "maxOutputTokens": out_budget,
            "responseMimeType": "application/json", "responseSchema": schema,
        },
    }
    response = request_fn(_endpoint(model), body, _headers(key))
    if response.get("status") == 429:
        raise QuotaExhausted("Gemini free-tier quota exhausted")
    if response.get("status") not in (None, 200):
        body_text = redact_secrets(str(response.get("body", "")))
        raise ModelError(f"Gemini error {response.get('status')}: {body_text[:200]}")
    try:
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
    except (KeyError, IndexError, ValueError) as exc:
        raise ModelError(f"unparseable model output: {exc}") from None
    tokens_in = estimate_tokens(prompt)
    tokens_out = estimate_tokens(text)
    if truncated:
        parsed["_truncated"] = True
    return parsed, tokens_in, tokens_out


_PATCH_SCHEMA: dict[str, Any] = {"type": "object"}
_TEXT_SCHEMA: dict[str, Any] = {"type": "object"}


def propose(spec: dict[str, Any] | None, intent: str, key: str,
            request_fn: Callable[..., Any]) -> dict[str, Any]:
    prompt = (
        "You translate a trading-idea edit into AlphaLab StrategyPatch ops. "
        f"Allowed ops: {', '.join(ALLOWED_OPS)}. Reply ONLY JSON "
        '{"ops": [...], "rationale": "..."}. Current spec:\n'
        f"{json.dumps(spec)[:12000]}\nIntent (max 1000 chars):\n{intent[:1000]}"
    )
    parsed, tin, tout = _generate(request_fn, MODEL_PROPOSE, key, prompt, BUDGETS["propose_out"], _PATCH_SCHEMA)
    ops = parsed.get("ops", [])
    if not isinstance(ops, list) or any(o.get("op") not in ALLOWED_OPS for o in ops if isinstance(o, dict)):
        raise ModelError("patch uses disallowed ops")
    return {"ops": ops, "rationale": str(parsed.get("rationale", "")),
            "provider": PROVIDER, "model": MODEL_PROPOSE,
            "tokens": tin + tout, "truncated": bool(parsed.get("_truncated"))}


def explain(spec: dict[str, Any], key: str, request_fn: Callable[..., Any]) -> dict[str, Any]:
    prompt = ("Explain this AlphaLab strategy precisely: entries, exits, sizing, filters. "
              "Reply ONLY JSON {\"text\": \"...\", \"citations\": [...]}. Spec:\n" + json.dumps(spec)[:6000])
    parsed, tin, tout = _generate(request_fn, MODEL_PROPOSE, key, prompt, BUDGETS["explain_out"], _TEXT_SCHEMA)
    return {"text": str(parsed.get("text", "")), "citations": list(parsed.get("citations", [])),
            "provider": PROVIDER, "model": MODEL_PROPOSE, "tokens": tin + tout}


def summarize(run_summaries: list[dict[str, Any]], key: str, request_fn: Callable[..., Any],
              pro: bool = False) -> dict[str, Any]:
    if len(run_summaries) > 4:
        raise ModelError("summarize caps at 4 runs per call")
    model = MODEL_SUMMARIZE_PRO if pro else MODEL_SUMMARIZE
    allowed_ids = {f"metrics.{k}" for s in run_summaries for k in s.get("metrics", {})}
    prompt = ("Summarize these AlphaLab backtests from the metrics ONLY. Never invent numbers. "
              "Cite every claim as metrics.<id>. Reply ONLY JSON {\"text\": \"...\", \"citations\": [...]}.\n"
              + json.dumps(run_summaries)[:20000])
    parsed, tin, tout = _generate(request_fn, model, key, prompt, BUDGETS["summarize_out"], _TEXT_SCHEMA)
    citations = list(parsed.get("citations", []))
    if any(c not in allowed_ids for c in citations):
        raise ModelError(f"ungrounded citations: {citations}")
    return {"text": str(parsed.get("text", "")), "citations": citations,
            "provider": PROVIDER, "model": model, "tokens": tin + tout}


def cache_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
