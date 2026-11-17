import { describe, expect, it } from "vitest";

import { loginSchema, registerSchema } from "@/lib/schemas";

const valid = {
  full_name: "Ada Scout",
  email: "ada@example.com",
  password: "long-enough-pass",
  confirm: "long-enough-pass",
  account_type: "standard" as const,
};

describe("loginSchema", () => {
  it("accepts valid input", () => {
    expect(
      loginSchema.safeParse({ email: "a@b.co", password: "x" }).success,
    ).toBe(true);
  });
  it("rejects bad email and empty password", () => {
    const r = loginSchema.safeParse({ email: "nope", password: "" });
    expect(r.success).toBe(false);
  });
});

describe("registerSchema", () => {
  it("accepts valid input", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true);
  });
  it("rejects short passwords", () => {
    expect(
      registerSchema.safeParse({
        ...valid,
        password: "short",
        confirm: "short",
      }).success,
    ).toBe(false);
  });
  it("rejects mismatched confirmation", () => {
    const r = registerSchema.safeParse({
      ...valid,
      confirm: "different-pass-1",
    });
    expect(r.success).toBe(false);
    if (!r.success) expect(r.error.issues[0].path).toEqual(["confirm"]);
  });
  it("rejects platform roles as account type", () => {
    expect(
      registerSchema.safeParse({ ...valid, account_type: "super_admin" })
        .success,
    ).toBe(false);
  });
});
