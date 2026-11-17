import type { ComponentProps } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  const styles = {
    primary: "bg-teal-600 text-white hover:bg-teal-700",
    secondary:
      "border border-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
    danger:
      "border border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-950",
  }[variant];
  return (
    <button
      className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-60 ${styles} ${className}`}
      {...props}
    />
  );
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-slate-200 p-4 dark:border-slate-800 ${className}`}
    >
      {children}
    </div>
  );
}

export function Stat({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <Card>
      <p className="text-xs uppercase tracking-wide opacity-60">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </Card>
  );
}

export function ErrorText({ children }: { children?: React.ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="text-sm text-red-600">
      {children}
    </p>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm opacity-70">
      {children}
    </p>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav
      className="flex items-center justify-between text-sm"
      aria-label="Pagination"
    >
      <span className="opacity-70">
        {total} result{total === 1 ? "" : "s"}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          Previous
        </Button>
        <span>
          Page {page} of {pages}
        </span>
        <Button
          variant="secondary"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
