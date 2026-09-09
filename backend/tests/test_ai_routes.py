"""AI route tests: ruled-path propose/confirm/explain/summarize/status (no key)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alphalab_api.app import create_app

from test_api import M15, SPEC, T0, backtest, make_dataset, make_strategy


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(tmp_path / "ai.sqlite3")
    with TestClient(app) as c:
        yield c


def test_status_offline_ruled(client: TestClient) -> None:
    status = client.get("/api/ai/status").json()
    assert status["keyConfigured"] is False and status["provider"] == "ruled"


def test_propose_confirm_ruled(client: TestClient) -> None:
    version_id = make_strategy(client)
    # ATR stop needed for the stop intent; craft one directly.
    spec = dict(SPEC)
    spec["indicators"] = [{"id": "atr", "kind": "ATR", "period": 14}]
    spec["exits"] = dict(SPEC["exits"], stopLoss={"kind": "atr", "atrMultiplier": 1.0})
    sid = client.post("/api/strategies", json={"name": "atr", "spec": spec}).json()["strategy"]["id"]
    version_id = client.get(f"/api/strategies/{sid}").json()["versions"][0]["id"]
    proposal = client.post("/api/ai/propose", json={
        "strategyVersionId": version_id, "intent": "change stop to 2 ATR"}).json()["proposal"]
    assert proposal["validation"]["ok"] is True
    assert proposal["provider"] == "ruled"
    confirmed = client.post("/api/ai/confirm", json={"proposalId": proposal["id"]}).json()["version"]
    detail = client.get(f"/api/strategies/{sid}").json()
    assert detail["strategy"]["currentVersionId"] == confirmed["id"]
    assert detail["versions"][-1]["spec"]["exits"]["stopLoss"] == {"kind": "atr", "atrMultiplier": 2.0}
    # Double-confirm is terminal.
    again = client.post("/api/ai/confirm", json={"proposalId": proposal["id"]})
    assert again.status_code == 409


def test_confirm_stale_patch_rejected(client: TestClient) -> None:
    version_id = make_strategy(client)
    proposal = client.post("/api/ai/propose", json={
        "strategyVersionId": version_id, "intent": "change risk to 2%"}).json()["proposal"]
    # Strategy moves on without the proposal...
    client.post("/api/ai/confirm", json={"proposalId": proposal["id"]})
    proposal2 = client.post("/api/ai/propose", json={
        "strategyVersionId": version_id, "intent": "change risk to 3%"}).json()["proposal"]
    stale = client.post("/api/ai/confirm", json={"proposalId": proposal2["id"]})
    assert stale.status_code == 409 and stale.json()["code"] == "STALE_PATCH"


def test_routes_import_without_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import sys

    import alphalab_api.routes_ai as routes_ai

    assert routes_ai._httpx_available() is True
    monkeypatch.setitem(sys.modules, "httpx", None)
    assert routes_ai._httpx_available() is False
    reloaded = importlib.reload(routes_ai)
    assert reloaded._httpx_available() is False


def test_propose_transport_fallback(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import alphalab_api.routes_ai as routes_ai

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(routes_ai, "_httpx_available", lambda: False)
    version_id = make_strategy(client)
    proposal = client.post("/api/ai/propose", json={
        "strategyVersionId": version_id, "intent": "change risk to 2%"}).json()["proposal"]
    assert proposal["provider"] == "ruled"
    assert proposal.get("fallbackReason") == "transport"
    assert proposal["validation"]["ok"] is True


def test_live_request_fn_sends_key_in_header(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    import alphalab_api.routes_ai as routes_ai

    calls: dict = {}

    class _Resp:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self) -> dict:
            return {}

    class _Client:
        def __init__(self, **kwargs: object) -> None:
            calls["timeout"] = kwargs.get("timeout")

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def post(self, url: str, json: object = None, headers: object = None) -> _Resp:
            calls.update(url=url, body=json, headers=headers)
            return _Resp()

    fake = types.ModuleType("httpx")
    fake.Client = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)
    out = routes_ai._live_request_fn("https://example.test/x", {"a": 1}, {"x-goog-api-key": "SECRET"})
    assert out["status"] == 200
    assert "SECRET" not in calls["url"] and "key=" not in calls["url"]
    assert calls["headers"] == {"x-goog-api-key": "SECRET"}


def test_explain_and_summarize_cached(client: TestClient) -> None:
    version_id = make_strategy(client)
    first = client.post("/api/ai/explain", json={"strategyVersionId": version_id}).json()
    assert "BTCUSD" in first["text"] and first["provider"] == "ruled"
    second = client.post("/api/ai/explain", json={"strategyVersionId": version_id}).json()
    assert second.get("cached") is True
    dataset_id = make_dataset(client)
    run = backtest(client, version_id, dataset_id)
    summary = client.post("/api/ai/summarize", json={"runIds": [run["id"]]}).json()
    assert "trades" in summary["text"] and summary["provider"] == "ruled"
    assert client.post("/api/ai/summarize", json={"runIds": []}).status_code == 400
