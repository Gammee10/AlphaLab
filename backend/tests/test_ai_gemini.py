"""Gemini adapter replay tests: recorded responses, no network, no key."""

from __future__ import annotations

import pytest

from alphalab_ai import gemini


def ok_response(payload: dict) -> dict:
    import json

    return {"status": 200, "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


def test_propose_valid_patch() -> None:
    seen = {}

    def transport(url: str, body: dict):
        seen["url"] = url
        assert "generateContent" in url
        return ok_response({"ops": [{"op": "setRisk", "field": "riskPerTradePct", "value": 1.0}],
                            "rationale": "lower risk"})

    out = gemini.propose({"a": 1}, "lower risk please", "key", transport)
    assert out["ops"][0]["field"] == "riskPerTradePct"
    assert out["provider"] == "gemini" and out["model"] == gemini.MODEL_PROPOSE
    assert out["tokens"] > 0 and not out["truncated"]


def test_propose_rejects_disallowed_ops() -> None:
    def transport(url: str, body: dict):
        return ok_response({"ops": [{"op": "exec", "code": "rm -rf"}], "rationale": "evil"})

    with pytest.raises(gemini.ModelError):
        gemini.propose({}, "evil", "key", transport)


def test_propose_quota_and_garbage() -> None:
    with pytest.raises(gemini.QuotaExhausted):
        gemini.propose({}, "x", "key", lambda u, b: {"status": 429})
    with pytest.raises(gemini.ModelError):
        gemini.propose({}, "x", "key", lambda u, b: {"status": 200, "candidates": []})
    with pytest.raises(gemini.ModelError):
        gemini.propose({}, "x", "key",
                       lambda u, b: {"status": 200, "candidates": [{"content": {"parts": [{"text": "not json"}]}}]})


def test_summarize_grounding() -> None:
    runs = [{"runId": "r1", "metrics": {"netProfit": "10", "tradeCount": 5}}]

    def good(url: str, body: dict):
        return ok_response({"text": "Up 10 over 5 trades.", "citations": ["metrics.netProfit"]})

    out = gemini.summarize(runs, "key", good)
    assert out["citations"] == ["metrics.netProfit"]

    def bad(url: str, body: dict):
        return ok_response({"text": "Sharpe 9.", "citations": ["metrics.sharpe"]})

    with pytest.raises(gemini.ModelError, match="ungrounded"):
        gemini.summarize(runs, "key", bad)

    with pytest.raises(gemini.ModelError, match="caps at 4"):
        gemini.summarize(runs * 5, "key", good)


def test_summarize_pro_model_and_explain() -> None:
    runs = [{"runId": "r1", "metrics": {"netProfit": "10"}}]
    seen = {}

    def transport(url: str, body: dict):
        seen["url"] = url
        return ok_response({"text": "t", "citations": ["metrics.netProfit"]})

    out = gemini.summarize(runs, "key", transport, pro=True)
    assert out["model"] == gemini.MODEL_SUMMARIZE_PRO and "gemini-pro-latest" in seen["url"]
    explained = gemini.explain({"specVersion": "1.0"}, "key", transport)
    assert explained["text"] == "t"
