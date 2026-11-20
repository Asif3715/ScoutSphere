import { describe, expect, it } from "vitest";

import { dayGroup, deadlineLabel, timeAgo } from "@/lib/format";

// A fixed "now": Wednesday 20 Nov 2026, 15:00 local time.
const NOW = new Date(2026, 10, 20, 15, 0, 0);
const at = (d: number, h = 12, m = 0) =>
  new Date(2026, 10, d, h, m).toISOString();

describe("timeAgo", () => {
  it("describes recent moments in words", () => {
    expect(timeAgo(at(20, 14, 59), NOW)).toBe("1 min ago");
    expect(timeAgo(new Date(NOW.getTime() - 20_000).toISOString(), NOW)).toBe(
      "just now",
    );
    expect(timeAgo(at(20, 10), NOW)).toBe("5 h ago");
  });

  it("counts calendar days, not 24h blocks", () => {
    // under 24h reads in hours; beyond that, by calendar day
    expect(timeAgo(at(19, 23), NOW)).toBe("16 h ago");
    expect(timeAgo(at(19, 9), NOW)).toBe("yesterday");
    // 1 day 16h earlier, but two calendar days back
    expect(timeAgo(at(18, 23), NOW)).toBe("2 days ago");
    expect(timeAgo(at(17), NOW)).toBe("3 days ago");
  });

  it("falls back to a date after a week", () => {
    expect(timeAgo(at(1), NOW)).toBe("1 Nov");
    expect(timeAgo(new Date(2025, 2, 12).toISOString(), NOW)).toBe(
      "12 Mar 2025",
    );
  });
});

describe("dayGroup", () => {
  it("groups by day", () => {
    expect(dayGroup(at(20, 1), NOW)).toBe("Today");
    expect(dayGroup(at(19), NOW)).toBe("Yesterday");
    expect(dayGroup(at(15), NOW)).toBe("This week");
    expect(dayGroup(at(2), NOW)).toBe("November 2026");
  });
});

describe("deadlineLabel", () => {
  it("handles missing and finished deadlines", () => {
    expect(deadlineLabel(null, {}, NOW)).toEqual({
      text: "No deadline",
      tone: "muted",
    });
    expect(deadlineLabel(at(10), { done: true }, NOW).tone).toBe("muted");
  });

  it("flags overdue work", () => {
    expect(deadlineLabel(at(18), {}, NOW)).toEqual({
      text: "Overdue by 2 days",
      tone: "bad",
    });
    expect(deadlineLabel(at(20, 9), {}, NOW).text).toBe("Overdue today");
  });

  it("warns when close and is calm when far", () => {
    expect(deadlineLabel(at(20, 18), {}, NOW).text).toBe("Due today");
    expect(deadlineLabel(at(21), {}, NOW).text).toBe("Due tomorrow");
    expect(deadlineLabel(at(23), {}, NOW)).toEqual({
      text: "Due in 3 days",
      tone: "warn",
    });
    expect(deadlineLabel(at(30), {}, NOW)).toEqual({
      text: "Due in 10 days",
      tone: "ok",
    });
  });
});
