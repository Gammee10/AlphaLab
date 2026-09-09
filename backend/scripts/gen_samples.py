"""Generate bundled synthetic samples (data/samples/). Offline-first demo data."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from alphalab_marketdata.synthetic import generate_synthetic, rows_to_csv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    samples = ROOT / "data" / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    eurusd = generate_synthetic("EURUSD", "M15", "2024-01-01T00:00:00Z", 2000, 7, 1.1000, volatility=0.0008)
    (samples / "eurusd_m15.csv").write_text(rows_to_csv(eurusd), encoding="utf-8")
    btc = generate_synthetic("BTCUSD", "H1", "2024-01-01T00:00:00Z", 1500, 21, 42000.0, volatility=150.0,
                             pip_size=1.0, with_volume=True)
    (samples / "btcusd_h1.csv").write_text(rows_to_csv(btc), encoding="utf-8")
    print(f"wrote samples to {samples}")


if __name__ == "__main__":
    main()
