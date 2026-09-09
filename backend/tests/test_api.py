"""API contract tests: full loop through HTTP (TestClient + tmp DB)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alphalab_api.app import create_app

CSV = """open_time,open,high,low,close,volume
2024-01-02T00:00:00Z,100,100,100,100,10
2024-01-02T00:15:00Z,101,101,100,101,10
2024-01-02T00:30:00Z,101,102,100,101,10
2024-01-02T00:45:00Z,102,103,101,102,10
2024-01-02T01:00:00Z,103,104,102,103,10
"""

SPEC = {
    "specVersion": "1.0",
    "universe": {"symbol": "BTCUSD", "timeframe": "M15"},
    "indicators": [{"id": "sma2", "kind": "SMA", "period": 2}],
    "entry": {
        "direction": "long", "logic": "all",
        "conditions": [{"id": "c1", "left": {"kind": "price", "field": "close"},
                        "op": ">", "right": {"kind": "price", "field": "close", "offsetBars": 1}}],
    },
    "exits": {
        "stopLoss": {"kind": "pips", "pips": 1}, "takeProfit": {"kind": "rr", "ratio": 2},
        "trailing": {"kind": "none"}, "timeStop": {"kind": "none"}, "oppositeSignalExit": False,
    },
    "filters": {},
    "risk": {"riskPerTradePct": 1, "maxNotionalMult": 5, "leverageMax": 10},
    "execution": {"fillBasis": "next_open"},
}

T0 = 1704153600000
M15 = 900_000


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(tmp_path / "api.sqlite3")
    with TestClient(app) as c:
        yield c


def make_strategy(client: TestClient, spec: dict | None = None) -> str:
    body = {"name": "s", "spec": spec or SPEC}
    r = client.post("/api/strategies", json=body)
    assert r.status_code == 201, r.text
    sid = r.json()["strategy"]["id"]
    detail = client.get(f"/api/strategies/{sid}").json()
    return detail["versions"][0]["id"]


def make_dataset(client: TestClient) -> str:
    r = client.post("/api/datasets/import", json={
        "filename": "t.csv", "csvText": CSV, "symbol": "BTCUSD", "timeframe": "M15"})
    assert r.status_code == 201, r.text
    return r.json()["dataset"]["id"]


def backtest(client: TestClient, version_id: str, dataset_id: str) -> dict:
    r = client.post("/api/backtests", json={
        "strategyVersionId": version_id, "datasetId": dataset_id,
        "config": {"startTime": T0, "endTime": T0 + 2 * M15, "initialCapital": "10000",
                   "costs": {"spreadBps": 0, "slippageBps": 0, "commissionPerUnit": 0}}})
    assert r.status_code == 200, r.text
    return r.json()["run"]


def test_health_and_templates(client: TestClient) -> None:
    assert client.get("/api/health").json()["ok"] is True
    templates = client.get("/api/templates").json()["templates"]
    assert {t["templateId"] for t in templates} == {
        "trend-pullback", "breakout-donchian", "mean-reversion-bollinger", "momentum-rsi"}
    preview = client.get("/api/templates/trend-pullback/preview").json()
    assert "emaFast" in preview["describe"]


def test_strategy_validation_errors(client: TestClient) -> None:
    bad = dict(SPEC)
    bad["specVersion"] = "9.9"
    r = client.post("/api/strategies", json={"name": "x", "spec": bad})
    assert r.status_code == 400 and r.json()["code"] == "STRATEGY_INVALID"
    reserved = dict(SPEC)
    reserved["reservedForFuture"] = {"partials": True}
    r = client.post("/api/strategies", json={"name": "x", "spec": reserved})
    assert r.status_code == 400 and r.json()["code"] == "NOT_SUPPORTED_IN_MVP"
    r = client.post("/api/strategies", json={"name": "x", "templateId": "nope", "params": {}})
    assert r.status_code == 400
    assert client.get("/api/strategies/missing").status_code == 404


def test_template_strategy_and_versioning(client: TestClient) -> None:
    r = client.post("/api/strategies", json={"name": "trend", "templateId": "trend-pullback", "params": {}})
    assert r.status_code == 201, r.text
    sid = r.json()["strategy"]["id"]
    detail = client.get(f"/api/strategies/{sid}").json()
    assert len(detail["versions"]) == 1
    v2 = client.post(f"/api/strategies/{sid}/versions", json={"spec": SPEC}).json()["version"]
    assert v2["versionNumber"] == 2
    assert client.get(f"/api/strategies/{sid}").json()["strategy"]["currentVersionId"] == v2["id"]


def test_dataset_import_dedupe_and_errors(client: TestClient) -> None:
    first = client.post("/api/datasets/import", json={
        "filename": "t.csv", "csvText": CSV, "symbol": "BTCUSD", "timeframe": "M15"}).json()
    second = client.post("/api/datasets/import", json={
        "filename": "t.csv", "csvText": CSV, "symbol": "BTCUSD", "timeframe": "M15"}).json()
    assert second["dataset"]["deduped"] is True
    assert second["dataset"]["id"] == first["dataset"]["id"]
    bad = client.post("/api/datasets/import", json={
        "filename": "t.csv", "csvText": "a,b\n1,2\n", "symbol": "BTCUSD", "timeframe": "M15"})
    assert bad.status_code == 400 and bad.json()["code"] == "DATASET_INVALID"
    assert client.get("/api/datasets/missing").status_code == 404
    listing = client.get("/api/datasets").json()["datasets"]
    assert len(listing) == 1 and listing[0]["barCount"] == 5


def test_backtest_one_trade_run(client: TestClient) -> None:
    run = backtest(client, make_strategy(client), make_dataset(client))
    assert run["engineVersion"] == "engine/1.0"
    assert run["metrics"]["tradeCount"] == 1
    assert run["metrics"]["netProfit"] == "-100"
    assert run["warnings"]["warmupBarsSkipped"] == 1  # signal bar 0 needs t-1
    assert any("next-open" in a for a in run["assumptions"])
    detail = client.get(f"/api/backtests/{run['id']}").json()["run"]
    assert len(detail["trades"]) == 1 and detail["trades"][0]["exitReason"] == "stop"
    page = client.get(f"/api/backtests/{run['id']}/trades?page=0&pageSize=1").json()
    assert page["total"] == 1 and len(page["trades"]) == 1
    # Resubmission dedupes by content hash.
    again = backtest(client, make_strategy(client), make_dataset(client))
    assert again["id"] == run["id"] and again["deduped"] is True


def test_backtest_missing_refs_404(client: TestClient) -> None:
    r = client.post("/api/backtests", json={
        "strategyVersionId": "missing", "datasetId": "missing",
        "config": {"startTime": T0, "endTime": T0 + M15}})
    assert r.status_code == 404


def test_job_cancel_terminal_409(client: TestClient) -> None:
    run = backtest(client, make_strategy(client), make_dataset(client))
    r = client.delete(f"/api/jobs/{run['jobId']}")
    assert r.status_code == 409 and r.json()["code"] == "JOB_NOT_CANCELLABLE"
    assert client.delete("/api/jobs/missing").status_code == 404
    assert client.get("/api/jobs/missing").status_code == 404


def test_experiment_diff_and_deltas(client: TestClient) -> None:
    version_id = make_strategy(client)
    dataset_id = make_dataset(client)
    run1 = backtest(client, version_id, dataset_id)
    spec2 = dict(SPEC)
    spec2["risk"] = dict(SPEC["risk"], riskPerTradePct=2)
    sid2 = client.post("/api/strategies", json={"name": "s2", "spec": spec2}).json()["strategy"]["id"]
    version2 = client.get(f"/api/strategies/{sid2}").json()["versions"][0]["id"]
    run2 = backtest(client, version2, dataset_id)
    exp = client.post("/api/experiments", json={
        "name": "e", "runIds": [run1["id"], run2["id"]], "baselineRunId": run1["id"]}).json()["experiment"]
    detail = client.get(f"/api/experiments/{exp['id']}").json()
    assert len(detail["runs"]) == 2
    assert any("riskPerTradePct" in line for line in detail["diff"])
    assert run2["id"] in detail["deltas"]
    bad = client.post("/api/experiments", json={"name": "e", "runIds": [run1["id"]]})
    assert bad.status_code == 400


def test_sweep_two_combos(client: TestClient) -> None:
    dataset_id = make_dataset(client)
    r = client.post("/api/experiments/sweep", json={
        "baseSpec": SPEC, "sweepParams": {"risk.riskPerTradePct": [1, 2]},
        "datasetIds": [dataset_id],
        "baseConfig": {"startTime": T0, "endTime": T0 + 2 * M15, "initialCapital": "10000"}})
    assert r.status_code == 201, r.text
    assert len(r.json()["runIds"]) == 2
    over = client.post("/api/experiments/sweep", json={
        "baseSpec": SPEC, "sweepParams": {"risk.riskPerTradePct": list(range(40))},
        "datasetIds": [dataset_id], "baseConfig": {}})
    assert over.status_code == 400
