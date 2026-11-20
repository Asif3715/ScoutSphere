import { describe, expect, it } from "vitest";

import { allowedStages, canMove } from "@/lib/stages";

describe("canMove", () => {
  it.each([
    ["discovered", "under_evaluation", true],
    ["discovered", "negotiation", true], // skipping ahead
    ["negotiation", "shortlisted", true], // stepping back
    ["discovered", "signed", false],
    ["trial_proposed", "signed", false],
    ["negotiation", "signed", true],
    ["signed", "archived", false],
    ["discovered", "rejected", true],
    ["rejected", "discovered", true],
    ["rejected", "shortlisted", false],
    ["archived", "negotiation", false],
    ["discovered", "discovered", false],
  ])("%s -> %s is %s", (a, b, ok) => {
    expect(canMove(a, b)).toBe(ok);
  });
  it("lists only legal next stages", () => {
    expect(allowedStages("rejected")).toEqual(["discovered"]);
    expect(allowedStages("signed")).toEqual([]);
    expect(allowedStages("negotiation")).toContain("signed");
    expect(allowedStages("discovered")).not.toContain("signed");
  });
});
