import { describe, expect, it } from "vitest";

import { safeNext } from "@/lib/redirect";

describe("safeNext", () => {
  it("allows same-site paths", () => {
    expect(safeNext("/invitations/accept?token=abc")).toBe(
      "/invitations/accept?token=abc",
    );
  });
  it("rejects open-redirect attempts", () => {
    for (const bad of [
      "https://evil.com",
      "//evil.com",
      "/\\evil.com",
      "javascript:alert(1)",
      "",
      null,
      undefined,
    ]) {
      expect(safeNext(bad)).toBe("/dashboard");
    }
  });
});
