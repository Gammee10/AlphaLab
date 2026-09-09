import { describe, expect, it } from "vitest";
import { deltaClass, fmtMoney, fmtPct, fmtRate, normalize, shortHash, toPoints } from "./format";

describe("format", () => {
  it("formats money strings", () => {
    expect(fmtMoney("150.5")).toBe("150.50");
    expect(fmtMoney("-100")).toBe("-100.00");
    expect(fmtMoney(null)).toBe("—");
    expect(fmtMoney(undefined)).toBe("—");
  });

  it("formats nullable ratios", () => {
    expect(fmtPct(0.015)).toBe("1.50%");
    expect(fmtPct(null)).toBe("—");
    expect(fmtRate(null)).toBe("— (n<30)");
    expect(fmtRate(2.345)).toBe("2.35");
  });

  it("normalizes overlays from own start", () => {
    const pts = normalize([[1, "100"], [2, "110"], [3, "90"]]);
    expect(pts[0].pct).toBe(0);
    expect(pts[1].pct).toBe(10);
    expect(pts[2].pct).toBe(-10);
    expect(normalize([])).toEqual([]);
  });

  it("maps deltas to classes", () => {
    expect(deltaClass(1)).toBe("up");
    expect(deltaClass(-0.5)).toBe("down");
    expect(deltaClass(0)).toBe("muted");
    expect(deltaClass(null)).toBe("muted");
  });

  it("shortens hashes and maps points", () => {
    expect(shortHash("abcdef123456")).toBe("abcdef12");
    expect(toPoints([[1, "10"]])).toEqual([{ t: 1, e: 10 }]);
  });
});
