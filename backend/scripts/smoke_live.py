"""Live smoke: walk the full research loop against the running API and print results."""
import httpx
import json

BASE = "http://127.0.0.1:4100"
s = httpx.Client(base_url=BASE, timeout=120.0)

print("=== 1. templates ===")
for t in s.get("/api/templates").json()["templates"]:
    print(f"  {t['templateId']:26s} v{t['templateVersion']}  {t['displayName']}")

print("\n=== 2. create strategy from trend-pullback ===")
st = s.post("/api/strategies", json={"name": "EURUSD trend pullback", "templateId": "trend-pullback", "params": {}}).json()
sid = st["strategy"]["id"]
d = s.get(f"/api/strategies/{sid}").json()
v = d["versions"][0]
print(f"  strategy {sid} v{v['versionNumber']} specHash {v['specHash'][:12]}...")

print("\n=== 3. import EURUSD M15 sample ===")
csv = open("data/samples/eurusd_m15.csv", encoding="utf-8").read()
imp = s.post("/api/datasets/import", json={"filename": "eurusd_m15.csv", "csvText": csv, "symbol": "EURUSD", "timeframe": "M15"}).json()
ds_id = imp["dataset"]["id"]
deduped = imp["dataset"].get("deduped", False)
full = s.get(f"/api/datasets/{ds_id}").json()
manifest = full["manifest"]
print(f"  dataset {ds_id}{' (deduped: content hash matched)' if deduped else ''}")
print(f"  {full['dataset']['barCount']} bars, dup dropped: {manifest.get('duplicatesDropped')}, rejected: {len(manifest.get('rowsRejected', []))}, gaps: {len(manifest.get('gaps', []))}")

print("\n=== 4. run backtest ===")
r = s.post("/api/backtests", json={
    "strategyVersionId": v["id"], "datasetId": ds_id,
    "config": {"startTime": 1704153600000, "endTime": 1706745600000, "initialCapital": "10000"},
})
print(f"  HTTP {r.status_code}")
run = r.json().get("run")
m = run["metrics"]
print(f"  engine {run['engineVersion']}  resultHash {run['resultHash'][:12]}...")
print(f"  trades: {m['tradeCount']}  net P&L: {m['netProfit']}  win rate: {m['winRate']}  PF: {m['profitFactor']}")
print(f"  maxDD: {m['maxDrawdown']} ({m['maxDrawdownPct']:.2f}%)  expectancy: {m['expectancy']}  streaks W/L: {m['maxWinStreak']}/{m['maxLossStreak']}")
print(f"  warnings: {json.dumps({k: val for k, val in run['warnings'].items() if val})}")

print("\n=== 5. trades ===")
tr = s.get(f"/api/backtests/{run['id']}/trades?page=0&pageSize=5").json()
for t in tr["trades"]:
    print(f"  {t['direction']:5s} qty={t['qty']:>6s} in={t['entryPrice']:>8s} out={t['exitPrice']:>8s} net={t['netPnl']:>10s} {t['exitReason']}")
print(f"  ... {tr['total']} total")

print("\n=== 6. AI propose + confirm (ruled provider, no key) ===")
p = s.post("/api/ai/propose", json={"strategyVersionId": v["id"], "intent": "change risk to 0.25%"}).json()["proposal"]
print(f"  provider={p['provider']} valid={p['validation']['ok']} ops={p['patch']['ops']}")
new_v = s.post("/api/ai/confirm", json={"proposalId": p["id"]}).json()["version"]
print(f"  confirmed -> v{new_v['versionNumber']} specHash {new_v['specHash'][:12]}...")

print("\n=== 7. backtest the new version, then compare ===")
r2 = s.post("/api/backtests", json={
    "strategyVersionId": new_v["id"], "datasetId": ds_id,
    "config": {"startTime": 1704153600000, "endTime": 1706745600000, "initialCapital": "10000"},
}).json()["run"]
m2 = r2["metrics"]
print(f"  trades: {m2['tradeCount']}  net P&L: {m2['netProfit']}  (was {m['netProfit']})")
exp = s.post("/api/experiments", json={"name": "risk sweep", "runIds": [run["id"], r2["id"]], "baselineRunId": run["id"]}).json()["experiment"]
detail = s.get(f"/api/experiments/{exp['id']}").json()
print(f"  experiment {exp['id']}")
for line in detail["diff"]:
    print(f"    diff: {line}")
for rid, deltas in detail["deltas"].items():
    print(f"    deltas {rid[:8]}...: {json.dumps(deltas)}")

print("\n=== 8. AI explain + summarize ===")
x = s.post("/api/ai/explain", json={"strategyVersionId": new_v["id"]}).json()
print(f"  [{x['provider']} · {x['model']} · {x['tokens']} tokens]")
print("  " + x["text"].replace("\n", "\n  ")[:600])
sm = s.post("/api/ai/summarize", json={"runIds": [r2["id"]]}).json()
print(f"  [{sm['provider']} · {sm['model']}]")
print("  " + sm["text"].replace("\n", "\n  ")[:600])

print("\n=== done ===")
open(".smoke_ids.txt", "w").write(f"{sid} {imp['dataset']['id']} {run['id']} {r2['id']}")
