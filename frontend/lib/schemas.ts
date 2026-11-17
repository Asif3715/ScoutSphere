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
