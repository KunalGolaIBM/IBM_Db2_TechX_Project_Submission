import { describe, expect, it } from "vitest";
import { checkName, formatAxis, formatCategory, formatDate, formatDateRange, formatMs, formatTimestamp, formatValue, parseUtc, UNDEFINED_VALUE } from "@/lib/formatters";

describe("formatValue", () => {
  it("formats USD with two decimals", () => expect(formatValue(111093.25, "USD")).toBe("$111,093.25"));
  it("formats COUNT as integer", () => expect(formatValue(426, "COUNT")).toBe("426"));
  it("treats RATIO as a fraction", () => expect(formatValue(0.076714, "RATIO", 4)).toBe("7.67%"));
  it("never turns null into zero", () => { expect(formatValue(null, "USD")).toBe(UNDEFINED_VALUE); expect(formatValue(undefined, "COUNT")).toBe(UNDEFINED_VALUE); });
  it("keeps real zero", () => expect(formatValue(0, "USD")).toBe("$0.00"));
});

describe("formatAxis", () => {
  it("compacts large USD", () => expect(formatAxis(140000, "USD")).toBe("$140K"));
  it("keeps small USD whole", () => expect(formatAxis(2000, "USD")).toBe("$2,000"));
  it("formats ratio axis", () => expect(formatAxis(0.05, "RATIO")).toBe("5.0%"));
});

describe("dates", () => {
  it("formats calendar dates without timezone shift", () => expect(formatDate("2026-01-01")).toBe("Jan 1, 2026"));
  it("formats ranges", () => expect(formatDateRange("2026-01-01", "2026-06-30")).toBe("Jan 1, 2026 – Jun 30, 2026"));
  it("treats offset-less audit timestamps as UTC", () => {
    expect(parseUtc("2026-11-07T20:36:39.384127").toISOString()).toBe("2026-11-07T20:36:39.384Z");
    expect(formatTimestamp("2026-11-07T20:36:39.384127")).toContain("20:36");
  });
  it("formats month categories", () => expect(formatCategory("2026-03")).toBe("Mar 2026"));
  it("leaves region codes alone", () => expect(formatCategory("EMEA")).toBe("EMEA"));
});

describe("misc", () => {
  it("formats durations", () => { expect(formatMs(0.2)).toBe("0.2 ms"); expect(formatMs(45.4)).toBe("45 ms"); expect(formatMs(1520)).toBe("1.52 s"); expect(formatMs(null)).toBe(UNDEFINED_VALUE); });
  it("keeps SQL acronym in check names", () => expect(checkName("sql_guard")).toBe("SQL guard"));
});
