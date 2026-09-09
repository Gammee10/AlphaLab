"""Probe which Gemini models this key can access (diagnostic only)."""
import json
import os

import httpx

KEY = os.environ["GEMINI_API_KEY"] = __import__("subprocess").run(
    ["powershell", "-NoProfile", "-Command",
     "[Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')"],
    capture_output=True, text=True).stdout.strip()
BASE = "https://generativelanguage.googleapis.com/v1beta"

with httpx.Client(timeout=30.0) as c:
    r = c.get(f"{BASE}/models", params={"key": KEY, "pageSize": 50})
    print(f"ListModels: HTTP {r.status_code}")
    if r.status_code == 200:
        models = r.json().get("models", [])
        usable = [m["name"] for m in models if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        print(f"  {len(usable)} models support generateContent:")
        for name in sorted(usable):
            print(f"    {name}")
    else:
        print(f"  {r.text[:400]}")
    for model in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"):
        rr = c.post(f"{BASE}/models/{model}:generateContent", params={"key": KEY},
                    json={"contents": [{"parts": [{"text": "Reply with the single word: ok"}]}]})
        print(f"generateContent {model}: HTTP {rr.status_code} {rr.text[:150] if rr.status_code != 200 else 'OK'}")
