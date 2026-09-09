"""Live smoke v2: full research loop with real Gemini calls (free-tier, BYOK).

Shows provider/model/tokens on every AI response. AI failures are displayed
honestly (validation rejection / quota fallback) rather than hidden — that is
the boundary working, not a bug.
"""
import json

import httpx

BASE = "http://127.0.0.1:4100"
s = httpx.Client(base_url=BASE, timeout=180.0)


def ai(label, path, body):
    print(f"\n=== {label} (live Gemini call) ===")
    r = s.post(path, json=body)
    print(f"  HTTP {r.status_code}")
    data = r.json()
    if r.status_code != 200:
        print(f"  {json.dumps(data)[:400]}")
        return None
    footer = f"[{data.get('provider')} · {data.get('model')} · {data.get('tokens', '?')} tokens]"
    if data.get("fallbackReason"):
        footer += f" FALLBACK: {data['fallbackReason']}"
    print(f"  {footer}")
    return data


print("=== 0. AI status ===")
print(" ", json.dumps(s.get("/api/ai/status").json()))

print("\n=== 1. fresh strategy from trend-pullback (defaults) ===")
st = s.post("/api/strategies", json={"name": "Gemini demo", "templateId": "trend-pullback", "params": {}}).json()
sid = st["strategy"]["id"]
v1 = s.get(f"/api/strategies/{sid}").json()["versions"][0]
print(f"  strategy {sid[:8]}... v{v1['versionNumber']} specHash {v1['specHash'][:12]}...")

print("\n=== 2. dataset (already imported — content-hash dedupe) ===")
ds = s.get("/api/datasets").json()["datasets"][0]
print(f"  {ds['symbol']} {ds['timeframe']} · {ds['barCount']} bars · hash {ds['barsHash'][:12]}...")

print("\n=== 3. backtest v1 ===")
run1 = s.post("/api/backtests", json={
    "strategyVersionId": v1["id"], "datasetId": ds["id"],
    "config": {"startTime": 1704153600000, "endTime": 1706745600000, "initialCapital": "10000"},
}).json()["run"]
m1 = run1["metrics"]
print(f"  {m1['tradeCount']} trades, net {m1['netProfit']}, warnings: {json.dumps({k: v for k, v in run1['warnings'].items() if v})}")

p = ai("4. Gemini propose — natural language", "/api/ai/propose", {
    "strategyVersionId": v1["id"],
    "intent": "I want to only trade during the London and New York sessions, and make my stop loss wider at 2 times ATR.",
})
if p:
    for op in p["patch"]["ops"]:
        print(f"    op: {json.dumps(op)[:160]}")
    print(f"    rationale: {p['patch'].get('rationale', '')[:200]}")
    if p["validation"]["ok"]:
        c = s.post("/api/ai/confirm", json={"proposalId": p["id"]})
        print(f"  confirm -> HTTP {c.status_code}")
        if c.status_code == 200:
            v2 = c.json()["version"]
            print(f"    new v{v2['versionNumber']} specHash {v2['specHash'][:12]}...")
            print("\n=== 5. backtest the Gemini-modified version ===")
            run2 = s.post("/api/backtests", json={
                "strategyVersionId": v2["id"], "datasetId": ds["id"],
                "config": {"startTime": 1704153600000, "endTime": 1706745600000, "initialCapital": "10000"},
            }).json()["run"]
            m2 = run2["metrics"]
            print(f"  {m2['tradeCount']} trades, net {m2['netProfit']} (v1 was {m1['tradeCount']} trades, {m1['netProfit']})")
            print(f"  warnings: {json.dumps({k: v for k, v in run2['warnings'].items() if v})}")
            exp = s.post("/api/experiments", json={"name": "gemini edit", "runIds": [run1["id"], run2["id"]],
                                                   "baselineRunId": run1["id"]}).json()["experiment"]
            detail = s.get(f"/api/experiments/{exp['id']}").json()
            print("\n=== 6. compare (what changed) ===")
            for line in detail["diff"]:
                print(f"    {line[:220]}")
            x = ai("7. Gemini explain", "/api/ai/explain", {"strategyVersionId": v2["id"]})
            if x:
                print("  " + x["text"].replace("\n", "\n  ")[:700])
            sm = ai("8. Gemini summarize", "/api/ai/summarize", {"runIds": [run2["id"]]})
            if sm:
                print("  " + sm["text"].replace("\n", "\n  ")[:700])
        else:
            print(f"  {c.text[:300]}")
    else:
        print("  proposal INVALID — boundary held, nothing applied:")
        for e in p["validation"]["errors"]:
            print(f"    {e['code']}: {e['message'][:200]}")

print("\n=== done ===")
