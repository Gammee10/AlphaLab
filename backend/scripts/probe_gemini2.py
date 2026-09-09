"""Probe current Flash models for generateContent (diagnostic only)."""
import subprocess

import httpx

KEY = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "[Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')"],
    capture_output=True, text=True).stdout.strip()
BASE = "https://generativelanguage.googleapis.com/v1beta"

with httpx.Client(timeout=60.0) as c:
    for model in ("gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.7-flash",
                  "gemini-3.8-flash", "gemini-2.5-flash-lite"):
        try:
            r = c.post(f"{BASE}/models/{model}:generateContent", params={"key": KEY},
                       json={"contents": [{"parts": [{"text": "Reply with the single word: ok"}]}]})
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"][:20]
                print(f"{model}: HTTP 200 OK -> {text!r}")
            else:
                print(f"{model}: HTTP {r.status_code} {r.text[:100]}")
        except Exception as exc:  # noqa: BLE001
            print(f"{model}: EXC {exc}")
