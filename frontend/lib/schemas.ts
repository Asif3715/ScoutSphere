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
