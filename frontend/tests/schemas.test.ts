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

import {
  clubPayload,
  clubSchema,
  inviteSchema,
  organizationSchema,
} from "@/lib/schemas";

describe("organizationSchema", () => {
  it("requires a name of at least 2 chars", () => {
    expect(organizationSchema.safeParse({ name: "A" }).success).toBe(false);
    expect(organizationSchema.safeParse({ name: "Alpha FC" }).success).toBe(
      true,
    );
  });
});

describe("clubSchema / clubPayload", () => {
  it("validates year and email", () => {
    expect(
      clubSchema.safeParse({ name: "X", founded_year: "1500" }).success,
    ).toBe(false);
    expect(
      clubSchema.safeParse({ name: "X", founded_year: "19x4" }).success,
    ).toBe(false);
    expect(
      clubSchema.safeParse({ name: "X", contact_email: "bad" }).success,
    ).toBe(false);
    expect(
      clubSchema.safeParse({
        name: "X",
        founded_year: "1904",
        contact_email: "a@b.co",
      }).success,
    ).toBe(true);
    expect(clubSchema.safeParse({ name: "" }).success).toBe(false);
  });
  it("converts blanks to null and the year to a number", () => {
    const p = clubPayload({
      name: " Alpha ",
      city: "",
      country: "UK",
      founded_year: "1904",
    });
    expect(p).toMatchObject({
      name: "Alpha",
      city: null,
      country: "UK",
      founded_year: 1904,
    });
    expect(
      clubPayload({ name: "B", founded_year: "" }).founded_year,
    ).toBeNull();
  });
});

describe("inviteSchema", () => {
  it("accepts organization roles only", () => {
    expect(
      inviteSchema.safeParse({ email: "a@b.co", role: "scout" }).success,
    ).toBe(true);
    expect(
      inviteSchema.safeParse({ email: "a@b.co", role: "super_admin" }).success,
    ).toBe(false);
  });
});

import {
  careerSchema,
  mediaSchema,
  playerPayload,
  playerSchema,
  teamSchema,
} from "@/lib/schemas";

const basePlayer = {
  full_name: "Luka Novak",
  date_of_birth: "2003-05-01",
  visibility: "private" as const,
};

describe("playerSchema / playerPayload", () => {
  it("accepts a minimal player", () => {
    expect(playerSchema.safeParse(basePlayer).success).toBe(true);
  });
  it("rejects bad name, future date, size and url", () => {
    expect(
      playerSchema.safeParse({ ...basePlayer, full_name: "L" }).success,
    ).toBe(false);
    expect(
      playerSchema.safeParse({ ...basePlayer, date_of_birth: "2999-01-01" })
        .success,
    ).toBe(false);
    expect(
      playerSchema.safeParse({ ...basePlayer, date_of_birth: "" }).success,
    ).toBe(false);
    expect(
      playerSchema.safeParse({ ...basePlayer, height_cm: "50" }).success,
    ).toBe(false);
    expect(
      playerSchema.safeParse({
        ...basePlayer,
        profile_picture_url: "javascript:alert(1)",
      }).success,
    ).toBe(false);
    expect(
      playerSchema.safeParse({
        ...basePlayer,
        secondary_positions: ["CM", "CB", "LB", "RB", "GK"],
      }).success,
    ).toBe(false);
  });
  it("converts blanks to null, numbers to numbers, and drops primary from secondary", () => {
    const p = playerPayload({
      ...basePlayer,
      height_cm: "181",
      weight_kg: "",
      nationality: " ",
      primary_position: "CM",
      secondary_positions: ["CM", "CAM"],
    });
    expect(p).toMatchObject({
      height_cm: 181,
      weight_kg: null,
      nationality: null,
      secondary_positions: ["CAM"],
    });
  });
});

describe("careerSchema", () => {
  const base = {
    club_id: "c1",
    spell_type: "permanent" as const,
    start_date: "2020-01-01",
  };
  it("validates dates and stats", () => {
    expect(careerSchema.safeParse(base).success).toBe(true);
    expect(
      careerSchema.safeParse({ ...base, end_date: "2019-01-01" }).success,
    ).toBe(false);
    expect(careerSchema.safeParse({ ...base, goals: "-1" }).success).toBe(
      false,
    );
    expect(careerSchema.safeParse({ ...base, club_id: "" }).success).toBe(
      false,
    );
  });
});

describe("mediaSchema / teamSchema", () => {
  it("only allows http(s) links", () => {
    expect(
      mediaSchema.safeParse({
        kind: "video",
        title: "x",
        url: "https://a.com/v",
      }).success,
    ).toBe(true);
    expect(
      mediaSchema.safeParse({
        kind: "video",
        title: "x",
        url: "javascript:alert(1)",
      }).success,
    ).toBe(false);
    expect(
      mediaSchema.safeParse({ kind: "audio", title: "x", url: "https://a.com" })
        .success,
    ).toBe(false);
  });
  it("requires a club and a name", () => {
    expect(
      teamSchema.safeParse({ club_id: "", name: "U19", team_type: "u19" })
        .success,
    ).toBe(false);
    expect(
      teamSchema.safeParse({ club_id: "c", name: "", team_type: "u19" })
        .success,
    ).toBe(false);
    expect(
      teamSchema.safeParse({ club_id: "c", name: "U19", team_type: "u19" })
        .success,
    ).toBe(true);
  });
});
