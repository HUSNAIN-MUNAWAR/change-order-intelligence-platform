import { describe, expect, it } from "vitest";

import { confidenceBand } from "@/lib/format";

const field = (value: unknown, confidence: number, validation: "valid" | "missing" | "conflict" = "valid") => ({
  value,
  confidence,
  evidence: null,
  method: value === null ? "missing" as const : "label" as const,
  validation,
  signals: [],
  alternatives: [],
});

describe("confidenceBand", () => {
  it("uses the documented high, medium and low thresholds", () => {
    expect(confidenceBand(field("CO-1", 0.8))).toBe("High");
    expect(confidenceBand(field("CO-1", 0.6))).toBe("Medium");
    expect(confidenceBand(field("CO-1", 0.59))).toBe("Low");
  });

  it("keeps missing and conflicting values distinct", () => {
    expect(confidenceBand(field(null, 0, "missing"))).toBe("Missing");
    expect(confidenceBand(field("18", 0.5, "conflict"))).toBe("Conflicting");
  });
});
