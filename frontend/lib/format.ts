/** Small, dependency-free date helpers for lists. All take an optional `now` for testing. */

const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

function plural(n: number, unit: string) {
  return `${n} ${unit}${n === 1 ? "" : "s"}`;
}

/** "just now", "5 min ago", "3 h ago", "yesterday", "4 days ago", then a short date. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const diff = now.getTime() - then.getTime();
  if (diff < MIN) return "just now";
  if (diff < HOUR) return `${Math.floor(diff / MIN)} min ago`;
  if (diff < DAY) return `${Math.floor(diff / HOUR)} h ago`;
  const days = calendarDays(then, now);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return shortDate(iso, now);
}

/** Whole calendar days between two instants, in local time (positive when b is later). */
export function calendarDays(a: Date, b: Date): number {
  const start = new Date(a.getFullYear(), a.getMonth(), a.getDate());
  const end = new Date(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((end.getTime() - start.getTime()) / DAY);
}

/** "12 Mar", or "12 Mar 2025" when not in the current year. */
export function shortDate(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    ...(d.getFullYear() !== now.getFullYear() ? { year: "numeric" } : {}),
  });
}

/** "12 Mar, 19:30" */
export function shortDateTime(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${shortDate(iso, now)}, ${time}`;
}

/** Heading for a group of items: "Today", "Yesterday", "This week", or "March 2025". */
export function dayGroup(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const days = calendarDays(d, now);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "This week";
  return d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

export type Deadline = {
  text: string;
  tone: "bad" | "warn" | "ok" | "muted";
};

/** A deadline described relative to now: "Overdue by 2 days", "Due today", "Due in 5 days". */
export function deadlineLabel(
  iso: string | null,
  opts: { done?: boolean } = {},
  now: Date = new Date(),
): Deadline {
  if (!iso) return { text: "No deadline", tone: "muted" };
  const d = new Date(iso);
  if (opts.done) return { text: shortDate(iso, now), tone: "muted" };
  const diff = d.getTime() - now.getTime();
  const days = calendarDays(now, d);
  if (diff < 0) {
    const late = Math.max(1, -days);
    return {
      text: -diff < DAY ? "Overdue today" : `Overdue by ${plural(late, "day")}`,
      tone: "bad",
    };
  }
  if (days === 0) return { text: "Due today", tone: "warn" };
  if (days === 1) return { text: "Due tomorrow", tone: "warn" };
  if (days <= 3) return { text: `Due in ${days} days`, tone: "warn" };
  return { text: `Due in ${days} days`, tone: "ok" };
}
