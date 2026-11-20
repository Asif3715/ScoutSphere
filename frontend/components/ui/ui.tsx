import type { ComponentProps } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  return <button className={`btn btn-${variant} ${className}`} {...props} />;
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
      className={`relative rounded-[3px] border border-line bg-surface/80 p-4 shadow-[0_1px_0_0_var(--line-soft)] backdrop-blur-[2px] ${className}`}
    >
      {children}
    </div>
  );
}

/** A scoreboard tile: tiny mono label over a big condensed figure. */
export function Stat({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="group relative overflow-hidden rounded-[3px] border border-line bg-surface/80 p-4">
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-1 bg-volt transition-all duration-300 group-hover:w-1.5"
      />
      <p className="eyebrow opacity-60">{label}</p>
      <p className="font-display mt-2 text-6xl leading-none font-extrabold tabular-nums [font-variation-settings:'opsz'_72]">
        {value}
      </p>
    </div>
  );
}

export function ErrorText({ children }: { children?: React.ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="flex items-start gap-2 text-sm text-bad">
      <span
        aria-hidden="true"
        className="mt-1 inline-block h-3 w-2 shrink-0 rounded-[1px] bg-bad"
      />
      {children}
    </p>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-[3px] border border-dashed border-line-strong p-8 text-center">
      <svg
        aria-hidden="true"
        viewBox="0 0 120 60"
        className="mx-auto mb-3 h-10 w-20 opacity-30"
      >
        <rect
          x="1"
          y="1"
          width="118"
          height="58"
          fill="none"
          stroke="currentColor"
        />
        <path d="M60 1v58" stroke="currentColor" />
        <circle cx="60" cy="30" r="10" fill="none" stroke="currentColor" />
      </svg>
      <p className="text-sm opacity-70">{children}</p>
    </div>
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
      className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-sm"
      aria-label="Pagination"
    >
      <span className="eyebrow opacity-70">
        {total} result{total === 1 ? "" : "s"}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          ← Prev
        </Button>
        <span className="font-mono text-xs tabular-nums">
          {String(page).padStart(2, "0")} / {String(pages).padStart(2, "0")}
        </span>
        <Button
          variant="secondary"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Next →
        </Button>
      </div>
    </nav>
  );
}
