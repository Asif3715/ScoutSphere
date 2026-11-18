import { label } from "@/lib/types";

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "approved"
      ? "bg-green-100 text-green-900"
      : status === "rejected" || status === "cancelled"
        ? "bg-red-100 text-red-900"
        : status === "submitted" || status === "under_review"
          ? "bg-blue-100 text-blue-900"
          : "bg-slate-200 text-slate-800";
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs ${tone}`}>
      {label(status)}
    </span>
  );
}
