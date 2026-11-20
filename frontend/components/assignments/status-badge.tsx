import { label } from "@/lib/types";

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "approved"
      ? "bg-ok-soft text-ok"
      : status === "rejected" || status === "cancelled"
        ? "bg-bad-soft text-bad"
        : status === "submitted" || status === "under_review"
          ? "bg-info-soft text-info"
          : "bg-surface-2 text-ink";
  return (
    <span className={`chip ${tone}`}>
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full bg-current"
      />
      {label(status)}
    </span>
  );
}
