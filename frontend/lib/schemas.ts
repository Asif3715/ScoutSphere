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

// ---- assignments, reports -------------------------------------------------------------
export const assignmentSchema = z.object({
  scout_id: z.string().min(1, "Choose a scout"),
  target_type: z.enum(["match", "competition", "player"]),
  target_id: z.string().min(1, "Choose a target"),
  title: z
    .string()
    .trim()
    .min(3, "Title must be at least 3 characters")
    .max(200),
  instructions: z.string().max(5000).optional(),
  criteria: z.string().max(3000).optional(),
  deadline: z
    .string()
    .optional()
    .refine(
      (v) => !v || new Date(v).getTime() > Date.now(),
      "The deadline must be in the future",
    ),
  assign_now: z.boolean().optional(),
});
export type AssignmentValues = z.infer<typeof assignmentSchema>;

export function assignmentPayload(v: AssignmentValues) {
  return {
    scout_id: v.scout_id,
    target_type: v.target_type,
    target_id: v.target_id,
    title: v.title.trim(),
    instructions: v.instructions?.trim() ? v.instructions.trim() : null,
    criteria: v.criteria?.trim() ? v.criteria.trim() : null,
    deadline: v.deadline ? toIsoUtc(v.deadline) : null,
    assign_now: !!v.assign_now,
  };
}

const rating = z
  .string()
  .refine(
    (v) => v === "" || (/^\d+$/.test(v) && +v >= 1 && +v <= 10),
    "1 to 10",
  )
  .optional();

export const reportSchema = z.object({
  player_id: z.string().min(1, "Choose a player"),
  match_id: z.string().optional(),
  observed_on: z
    .string()
    .min(1, "Date observed is required")
    .refine(
      (v) => v <= new Date().toISOString().slice(0, 10),
      "Cannot be in the future",
    ),
  position_observed: z.string().optional(),
  recommendation: z.string().optional(),
  strengths: z.string().max(5000).optional(),
  weaknesses: z.string().max(5000).optional(),
  development_areas: z.string().max(5000).optional(),
  general_observations: z.string().max(5000).optional(),
  ratings: z.record(z.string(), rating),
});
export type ReportValues = z.infer<typeof reportSchema>;

export function reportPayload(v: ReportValues) {
  const blank = (s?: string) => (s && s.trim() !== "" ? s.trim() : null);
  const ratings: Record<string, number> = {};
  for (const [k, val] of Object.entries(v.ratings ?? {}))
    if (val && val !== "") ratings[k] = Number(val);
  return {
    observed_on: v.observed_on,
    position_observed: blank(v.position_observed),
    recommendation: blank(v.recommendation),
    strengths: blank(v.strengths),
    weaknesses: blank(v.weaknesses),
    development_areas: blank(v.development_areas),
    general_observations: blank(v.general_observations),
    ratings,
  };
}

/** What is still missing before a report can be submitted (mirrors the backend rules). */
export function missingForSubmit(v: {
  ratings: Record<string, number>;
  recommendation: string | null;
  general_observations: string | null;
}) {
  const missing: string[] = [];
  if (Object.keys(v.ratings).length < 3) missing.push("at least 3 ratings");
  if (!v.recommendation) missing.push("a recommendation");
  if (!(v.general_observations ?? "").trim())
    missing.push("general observations");
  return missing;
}

export const reviewSchema = z
  .object({
    decision: z.enum(["approved", "revision_requested", "rejected"]),
    comment: z.string().max(3000).optional(),
  })
  .refine((v) => v.decision === "approved" || !!v.comment?.trim(), {
    path: ["comment"],
    message: "Explain your decision to the scout",
  });
export type ReviewValues = z.infer<typeof reviewSchema>;

// ---- recruitment -----------------------------------------------------------------------
export const requirementSchema = z
  .object({
    title: z
      .string()
      .trim()
      .min(3, "Title must be at least 3 characters")
      .max(200),
    position: z.string().min(1, "Choose a position"),
    min_age: numStr("Minimum age", 8, 60),
    max_age: numStr("Maximum age", 8, 60),
    nationality: z.string().trim().max(100).optional(),
    preferred_foot: z.enum(["", "left", "right", "both"]).optional(),
    min_appearances: numStr("Appearances", 0, 5000),
    budget_min: z.string().trim().regex(/^\d*$/, "Whole number").optional(),
    budget_max: z.string().trim().regex(/^\d*$/, "Whole number").optional(),
    currency: z
      .string()
      .trim()
      .regex(/^([A-Za-z]{3})?$/, "Three letters, e.g. EUR")
      .optional(),
    contract_notes: z.string().max(3000).optional(),
    instructions: z.string().max(5000).optional(),
    priority: z.enum(["low", "medium", "high", "urgent"]),
    attributes: z.record(z.string(), rating),
  })
  .superRefine((v, ctx) => {
    const n = (s?: string) => (s && s !== "" ? Number(s) : null);
    if (
      n(v.min_age) != null &&
      n(v.max_age) != null &&
      n(v.min_age)! > n(v.max_age)!
    )
      ctx.addIssue({
        code: "custom",
        path: ["max_age"],
        message: "Maximum age must not be below the minimum",
      });
    if (
      n(v.budget_min) != null &&
      n(v.budget_max) != null &&
      n(v.budget_min)! > n(v.budget_max)!
    )
      ctx.addIssue({
        code: "custom",
        path: ["budget_max"],
        message: "Maximum budget must not be below the minimum",
      });
    if ((n(v.budget_min) != null || n(v.budget_max) != null) && !v.currency)
      ctx.addIssue({
        code: "custom",
        path: ["currency"],
        message: "Choose a currency for the budget",
      });
  });
export type RequirementValues = z.infer<typeof requirementSchema>;

export function requirementPayload(v: RequirementValues) {
  const blank = (s?: string) => (s && s.trim() !== "" ? s.trim() : null);
  const num = (s?: string) => (s && s.trim() !== "" ? Number(s) : null);
  const attributes: Record<string, number> = {};
  for (const [k, val] of Object.entries(v.attributes ?? {}))
    if (val && val !== "") attributes[k] = Number(val);
  return {
    title: v.title.trim(),
    position: v.position,
    min_age: num(v.min_age),
    max_age: num(v.max_age),
    nationality: blank(v.nationality),
    preferred_foot: blank(v.preferred_foot),
    min_appearances: num(v.min_appearances),
    budget_min: num(v.budget_min),
    budget_max: num(v.budget_max),
    currency: blank(v.currency)?.toUpperCase() ?? null,
    contract_notes: blank(v.contract_notes),
    instructions: blank(v.instructions),
    priority: v.priority,
    attributes,
  };
}

export const shortlistSchema = z.object({
  name: z.string().trim().min(2, "Name must be at least 2 characters").max(200),
  description: z.string().max(3000).optional(),
  priority: z.enum(["low", "medium", "high", "urgent"]),
  requirement_id: z.string().optional(),
});
export type ShortlistValues = z.infer<typeof shortlistSchema>;

export const stageMoveSchema = z.object({
  to: z.string().min(1, "Choose a stage"),
  note: z.string().max(500).optional(),
});

/** "passing:7" filters from the discovery form. */
export function ratingFilters(values: Record<string, string>): string[] {
  return Object.entries(values)
    .filter(([, v]) => v && /^\d+$/.test(v) && +v >= 1 && +v <= 10)
    .map(([k, v]) => `${k}:${v}`);
}
