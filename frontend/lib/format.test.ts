import { describe, expect, it } from "vitest";

import { UNAVAILABLE, formatMetric, formatObservedChange } from "./format";

describe("formatMetric", () => {
  it("renders null as unavailable, not 0", () => {
    expect(formatMetric(null)).toBe(UNAVAILABLE);
    expect(formatMetric(undefined)).toBe(UNAVAILABLE);
  });

  it("renders a real zero as 0", () => {
    expect(formatMetric(0)).toBe("0");
  });

  it("formats large numbers", () => {
    expect(formatMetric(12000)).toBe("12,000");
  });
});

describe("formatObservedChange", () => {
  it("reports insufficient samples", () => {
    expect(formatObservedChange(null, null)).toContain("样本不足");
  });

  it("does not compute rate when previous is zero/missing", () => {
    expect(formatObservedChange(150, null)).toContain("不计算变化率");
  });

  it("renders delta and rate", () => {
    expect(formatObservedChange(50, 50)).toContain("+50");
  });
});
