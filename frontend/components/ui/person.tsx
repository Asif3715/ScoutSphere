import { initials } from "@/lib/media";
import { ROLE_LABELS } from "@/lib/types";

/** What each organization role is for, in one line, plus its badge tone. */
export const ROLE_INFO: Record<
  string,
  { short: string; summary: string; tone: string }
> = {
  club_owner: {
    short: "Owner",
    summary: "Full control, including organization settings and other owners.",
    tone: "bg-volt text-volt-ink",
  },
  club_admin: {
    short: "Admin",
    summary:
      "Runs the organization day to day: members, clubs, players, scouting and recruitment.",
    tone: "bg-info-soft text-info",
  },
  recruitment_manager: {
    short: "Recruitment",
    summary:
      "Sets requirements, assigns scouts, reviews reports and manages pipelines and shortlists.",
    tone: "bg-ok-soft text-ok",
  },
  scout: {
    short: "Scout",
    summary:
      "Works on their own assignments and writes scouting reports. Can search players.",
    tone: "bg-warn-soft text-warn",
  },
  coach: {
    short: "Coach",
    summary:
      "Sees squads, players, matches, reports and recruitment, and evaluates trials.",
    tone: "bg-surface-2 text-ink",
  },
};

export function roleName(role: string) {
  return ROLE_LABELS[role] ?? role.replace(/_/g, " ");
}

/** A role chip. `compact` shows the short form ("Owner") for tight spaces. */
export function RoleBadge({
  role,
  compact = false,
  className = "",
}: {
  role: string;
  compact?: boolean;
  className?: string;
}) {
  const info = ROLE_INFO[role];
  return (
    <span
      title={info?.summary}
      className={`chip ${info?.tone ?? "bg-surface-2 text-ink"} ${className}`}
    >
      {compact ? (info?.short ?? roleName(role)) : roleName(role)}
    </span>
  );
}

// Muted, pitch-friendly tints; picked by name so a person keeps their colour everywhere.
const TINTS = [
  "bg-[#1f4d36] text-[#d8f5c4]",
  "bg-[#24405f] text-[#d3e4ff]",
  "bg-[#5c3b1c] text-[#ffe2bb]",
  "bg-[#4a2840] text-[#ffd6ef]",
  "bg-[#3a3f1a] text-[#eef6b4]",
  "bg-[#203c3f] text-[#c9f3f0]",
];

function tintFor(name: string) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

const SIZES = {
  xs: "h-6 w-6 text-[0.58rem]",
  sm: "h-8 w-8 text-[0.68rem]",
  md: "h-10 w-10 text-sm",
} as const;

/** Initials in a round tile: used for staff (players get the square PlayerAvatar). */
export function PersonAvatar({
  name,
  size = "sm",
  className = "",
}: {
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`inline-grid shrink-0 place-items-center rounded-full font-mono font-semibold tracking-wide ${tintFor(name)} ${SIZES[size]} ${className}`}
    >
      {initials(name)}
    </span>
  );
}
