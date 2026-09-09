"""Proof the backtest trades: fresh template defaults, live API, hand-checkable first trade."""
import httpx

s = httpx.Client(base_url="http://127.0.0.1:4100", timeout=180.0)
sid = s.post("/api/strategies", json={"name": "proof", "templateId": "trend-pullback", "params": {}}).json()["strategy"]["id"]
ver = s.get(f"/api/strategies/{sid}").json()["versions"][0]["id"]
ds = s.get("/api/datasets").json()["datasets"][0]["id"]
cfg = {"startTime": 1704153600000, "endTime": 1706745600000, "initialCapital": "10000"}
r1 = s.post("/api/backtests", json={"strategyVersionId": ver, "datasetId": ds, "config": cfg}).json()["run"]
r2 = s.post("/api/backtests", json={"strategyVersionId": ver, "datasetId": ds, "config": cfg}).json()
print("trades:", r1["metrics"]["tradeCount"], "net:", r1["metrics"]["netProfit"])
print("determinism: same resultHash twice ->", r1["resultHash"] == r2["run"]["resultHash"], "| deduped:", r2["run"].get("deduped"))
t = s.get(f"/api/backtests/{r1['id']}/trades?page=0&pageSize=1").json()["trades"][0]
print("first trade:", {k: t[k] for k in ("direction", "qty", "entryPrice", "exitPrice", "netPnl", "exitReason", "ambiguous")})
print("warnings:", {k: v for k, v in r1["warnings"].items() if v})
