import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

// Mirrors the backend rules (min 10 chars); the backend remains the authority.
export const registerSchema = z
  .object({
    full_name: z.string().trim().min(1, "Name is required").max(200),
    email: z.string().min(1, "Email is required").email("Enter a valid email"),
    password: z.string().min(10, "Use at least 10 characters").max(128),
    confirm: z.string(),
    account_type: z.enum(["standard", "player", "agent"]),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.infer<typeof registerSchema>;

export const organizationSchema = z.object({
  name: z.string().trim().min(2, "Name must be at least 2 characters").max(200),
  description: z.string().max(2000).optional(),
});
export type OrganizationValues = z.infer<typeof organizationSchema>;

const optionalText = (max: number) => z.string().trim().max(max).optional();

export const clubSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  short_name: optionalText(50),
  country: optionalText(100),
  city: optionalText(100),
  founded_year: z
    .string()
    .trim()
    .refine(
      (v) => v === "" || (/^\d{4}$/.test(v) && +v >= 1800 && +v <= 2100),
      "Enter a year between 1800 and 2100",
    )
    .optional(),
  website: optionalText(300),
  contact_email: z
    .string()
    .trim()
    .refine(
      (v) => v === "" || z.string().email().safeParse(v).success,
      "Enter a valid email",
    )
    .optional(),
  contact_phone: optionalText(50),
  description: optionalText(4000),
});
export type ClubValues = z.infer<typeof clubSchema>;

/** Turns form strings into the API payload: blank -> null, year -> number. */
export function clubPayload(v: ClubValues) {
  const blank = (s?: string) => (s && s.trim() !== "" ? s.trim() : null);
  return {
    name: v.name.trim(),
    short_name: blank(v.short_name),
    country: blank(v.country),
    city: blank(v.city),
    founded_year:
      v.founded_year && v.founded_year.trim() !== ""
        ? Number(v.founded_year)
        : null,
    website: blank(v.website),
    contact_email: blank(v.contact_email),
    contact_phone: blank(v.contact_phone),
    description: blank(v.description),
  };
}

export const inviteSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  role: z.enum([
    "club_admin",
    "recruitment_manager",
    "scout",
    "coach",
    "club_owner",
  ]),
});
export type InviteValues = z.infer<typeof inviteSchema>;

// ---- players & teams ------------------------------------------------------------------
const numStr = (label: string, min: number, max: number) =>
  z
    .string()
    .trim()
    .refine(
      (v) => v === "" || (/^\d+$/.test(v) && +v >= min && +v <= max),
      `${label} must be ${min}-${max}`,
    )
    .optional();

export const playerSchema = z.object({
  full_name: z
    .string()
    .trim()
    .min(2, "Name must be at least 2 characters")
    .max(200),
  date_of_birth: z
    .string()
    .min(1, "Date of birth is required")
    .refine(
      (v) => !Number.isNaN(Date.parse(v)) && new Date(v) < new Date(),
      "Must be a past date",
    ),
  nationality: z.string().trim().max(100).optional(),
  height_cm: numStr("Height", 120, 230),
  weight_kg: numStr("Weight", 30, 160),
  preferred_foot: z.enum(["", "left", "right", "both"]).optional(),
  primary_position: z.string().optional(),
  secondary_positions: z
    .array(z.string())
    .max(4, "At most 4 secondary positions")
    .optional(),
  visibility: z.enum(["private", "network", "public"]),
  profile_picture_url: z
    .string()
    .trim()
    .refine(
      (v) => v === "" || /^https?:\/\/\S+$/i.test(v),
      "Must start with http:// or https://",
    )
    .optional(),
  biography: z.string().max(5000).optional(),
});
export type PlayerValues = z.infer<typeof playerSchema>;

export function playerPayload(v: PlayerValues) {
  const blank = (s?: string) => (s && s.trim() !== "" ? s.trim() : null);
  const num = (s?: string) => (s && s.trim() !== "" ? Number(s) : null);
  const primary = blank(v.primary_position);
  return {
    full_name: v.full_name.trim(),
    date_of_birth: v.date_of_birth,
    nationality: blank(v.nationality),
    height_cm: num(v.height_cm),
    weight_kg: num(v.weight_kg),
    preferred_foot: blank(v.preferred_foot),
    primary_position: primary,
    secondary_positions: (v.secondary_positions ?? []).filter(
      (p) => p !== primary,
    ),
    visibility: v.visibility,
    profile_picture_url: blank(v.profile_picture_url),
    biography: blank(v.biography),
  };
}

export const careerSchema = z
  .object({
    club_id: z.string().min(1, "Choose a club"),
    team_label: z.string().trim().max(100).optional(),
    spell_type: z.enum(["permanent", "loan", "youth", "trial"]),
    start_date: z.string().min(1, "Start date is required"),
    end_date: z.string().optional(),
    appearances: numStr("Appearances", 0, 2000),
    goals: numStr("Goals", 0, 2000),
    assists: numStr("Assists", 0, 2000),
  })
  .refine((v) => !v.end_date || v.end_date >= v.start_date, {
    path: ["end_date"],
    message: "End date cannot be before start date",
  });
export type CareerValues = z.infer<typeof careerSchema>;

export const mediaSchema = z.object({
  kind: z.enum(["video", "image", "document"]),
  title: z.string().trim().min(1, "Title is required").max(200),
  url: z
    .string()
    .trim()
    .regex(/^https?:\/\/\S+$/i, "Must start with http:// or https://"),
});
export type MediaValues = z.infer<typeof mediaSchema>;

export const teamSchema = z.object({
  club_id: z.string().min(1, "Choose a club"),
  name: z.string().trim().min(1, "Name is required").max(150),
  team_type: z.string().min(1),
});
export type TeamValues = z.infer<typeof teamSchema>;

// ---- scouts, competitions, matches ----------------------------------------------------
export const scoutSchema = z.object({
  user_id: z.string().optional(),
  bio: z.string().max(3000).optional(),
  experience_years: numStr("Experience", 0, 60),
  positions: z.array(z.string()).optional(),
  age_groups: z.array(z.string()).optional(),
  regions: z.string().optional(), // comma separated in the form
});
export type ScoutValues = z.infer<typeof scoutSchema>;

export function scoutPayload(v: ScoutValues) {
  const regions = (v.regions ?? "")
    .split(",")
    .map((r) => r.trim())
    .filter(Boolean);
  return {
    bio: v.bio?.trim() ? v.bio.trim() : null,
    experience_years:
      v.experience_years && v.experience_years.trim() !== ""
        ? Number(v.experience_years)
        : null,
    positions: v.positions ?? [],
    age_groups: v.age_groups ?? [],
    regions: [...new Set(regions)],
  };
}

export const competitionSchema = z.object({
  name: z.string().trim().min(2, "Name must be at least 2 characters").max(200),
  country: z.string().trim().max(100).optional(),
  competition_type: z.enum([
    "league",
    "cup",
    "friendly",
    "youth_league",
    "international",
    "other",
  ]),
});
export type CompetitionValues = z.infer<typeof competitionSchema>;

export const seasonSchema = z
  .object({
    name: z.string().trim().min(1, "Name is required").max(50),
    start_date: z.string().min(1, "Start date is required"),
    end_date: z.string().min(1, "End date is required"),
  })
  .refine((v) => v.end_date >= v.start_date, {
    path: ["end_date"],
    message: "End date cannot be before start date",
  });
export type SeasonValues = z.infer<typeof seasonSchema>;

export const matchSchema = z
  .object({
    season_id: z.string().min(1, "Choose a season"),
    home_club_id: z.string().min(1, "Choose the home club"),
    away_club_id: z.string().min(1, "Choose the away club"),
    kickoff_at: z.string().min(1, "Kick-off time is required"),
    venue: z.string().trim().max(200).optional(),
    round_label: z.string().trim().max(50).optional(),
  })
  .refine((v) => v.home_club_id !== v.away_club_id, {
    path: ["away_club_id"],
    message: "A club cannot play itself",
  });
export type MatchValues = z.infer<typeof matchSchema>;

/** datetime-local value (no zone) -> ISO string in UTC. */
export function toIsoUtc(local: string): string {
  return new Date(local).toISOString();
}

export const eventSchema = z.object({
  event_type: z.enum([
    "goal",
    "own_goal",
    "penalty",
    "yellow_card",
    "red_card",
    "substitution",
  ]),
  minute: z
    .string()
    .regex(/^\d{1,3}$/, "Enter a minute")
    .refine((v) => +v <= 150, "Max 150"),
  club_id: z.string().min(1, "Choose a club"),
  description: z.string().max(300).optional(),
});
export type EventValues = z.infer<typeof eventSchema>;

export const statsSideSchema = z
  .record(z.string(), z.string())
  .superRefine((v, ctx) => {
    for (const [k, val] of Object.entries(v)) {
      if (val.trim() !== "" && !/^\d+$/.test(val.trim()))
        ctx.addIssue({ code: "custom", path: [k], message: "Whole number" });
    }
    const n = (k: string) => (v[k]?.trim() ? Number(v[k]) : null);
    if (n("possession_pct") != null && n("possession_pct")! > 100)
      ctx.addIssue({
        code: "custom",
        path: ["possession_pct"],
        message: "Max 100",
      });
    if (
      n("shots") != null &&
      n("shots_on_target") != null &&
      n("shots_on_target")! > n("shots")!
    )
      ctx.addIssue({
        code: "custom",
        path: ["shots_on_target"],
        message: "Cannot exceed shots",
      });
  });
