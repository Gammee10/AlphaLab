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
