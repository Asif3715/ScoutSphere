import { label } from "@/lib/types";

// One palette for every workflow status in the app (assignments, reports, requirements,
// matches), so the same word always looks the same.
const TONES: Record<string, string> = {
  approved: "bg-ok-soft text-ok",
  fulfilled: "bg-ok-soft text-ok",
  finished: "bg-ok-soft text-ok",
  signed: "bg-ok-soft text-ok",
  rejected: "bg-bad-soft text-bad",
  cancelled: "bg-bad-soft text-bad",
  submitted: "bg-info-soft text-info",
  under_review: "bg-info-soft text-info",
  live: "bg-bad text-white",
  in_progress: "bg-warn-soft text-warn",
  revision_requested: "bg-warn-soft text-warn",
  on_hold: "bg-warn-soft text-warn",
  postponed: "bg-warn-soft text-warn",
  draft: "border border-dashed border-line-strong text-ink/70",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = TONES[status] ?? "chip-outline";
  return (
    <span className={`chip ${tone}`}>
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full bg-current ${status === "live" ? "live-dot" : ""}`}
      />
      {label(status)}
    </span>
  );
}

const RECOMMENDATION_TONES: Record<string, string> = {
  strongly_recommend: "text-ok font-semibold",
  recommend: "text-ok",
  monitor: "text-warn",
  not_recommended: "text-bad",
};

/** A scout's verdict, coloured from "strongly recommend" (green) to "not recommended" (red). */
export function RecommendationText({ value }: { value: string | null }) {
  if (!value) return <span className="opacity-40">—</span>;
  return (
    <span
      className={`whitespace-nowrap capitalize ${RECOMMENDATION_TONES[value] ?? ""}`}
    >
      {label(value)}
    </span>
  );
}

const PRIORITY_TONES: Record<string, string> = {
  urgent: "bg-bad text-white",
  high: "bg-bad-soft text-bad",
  medium: "bg-warn-soft text-warn",
  low: "chip-outline",
};

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`chip ${PRIORITY_TONES[priority] ?? "chip-outline"}`}>
      {priority}
    </span>
  );
}
