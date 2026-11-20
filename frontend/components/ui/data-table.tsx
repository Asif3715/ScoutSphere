"use client";

import Link from "next/link";
import { useId, useState, type ComponentProps } from "react";

import { SearchIcon, SettingsIcon } from "@/components/ui/icons";

/** Page title block: small section label, big title, a one-line summary and actions. */
export function PageHeader({
  eyebrow,
  title,
  meta,
  actions,
}: {
  eyebrow?: string;
  title: string;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-line pb-5">
      <div className="min-w-0 space-y-2">
        {eyebrow && <p className="eyebrow text-link">{eyebrow}</p>}
        <h1>{title}</h1>
        {meta && <p className="text-sm opacity-70">{meta}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

/**
 * The frame every list sits in: an optional toolbar (search and filters), the table, and a
 * footer (usually pagination). Wide tables scroll sideways inside the frame on phones.
 */
export function TableCard({
  search,
  toolbar,
  footer,
  children,
  className = "",
}: {
  /** Always visible, first in the toolbar. */
  search?: React.ReactNode;
  /** Filters: inline on larger screens, folded behind a "Filters" button on phones. */
  toolbar?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const filtersId = useId();
  return (
    <section className={`table-card ${className}`}>
      {(search || toolbar) && (
        <div className="table-toolbar">
          {search}
          {toolbar && (
            <>
              <button
                type="button"
                className="btn btn-secondary h-9 sm:hidden"
                aria-expanded={open}
                aria-controls={filtersId}
                onClick={() => setOpen((o) => !o)}
              >
                <SettingsIcon className="h-4 w-4" />
                Filters
              </button>
              <div
                id={filtersId}
                className={`${open ? "flex" : "hidden"} w-full flex-wrap items-end gap-3 sm:contents`}
              >
                {toolbar}
              </div>
            </>
          )}
        </div>
      )}
      <div className="overflow-x-auto">{children}</div>
      {footer && <div className="table-footer">{footer}</div>}
    </section>
  );
}

/** A labelled filter control for a toolbar. */
export function FilterField({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      <span className="eyebrow opacity-60">{label}</span>
      {children}
    </label>
  );
}

/** Search box with a leading icon. */
export function SearchInput({
  label = "Search",
  className = "",
  ...props
}: ComponentProps<"input"> & { label?: string }) {
  return (
    <label className={`relative flex items-center ${className}`}>
      <span className="sr-only">{label}</span>
      <SearchIcon className="pointer-events-none absolute left-2.5 h-4 w-4 opacity-50" />
      <input type="search" className="field-input w-full pl-8" {...props} />
    </label>
  );
}

/** Placeholder rows shown while a list loads, so the layout doesn't jump. */
export function SkeletonRows({
  cols,
  rows = 6,
}: {
  cols: number;
  rows?: number;
}) {
  return (
    <tbody aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} className="pointer-events-none">
          {Array.from({ length: cols }, (_, c) => (
            <td key={c}>
              <span
                className="skeleton block h-3.5"
                style={{
                  width: `${c === 0 ? 70 : 40 + ((r * 7 + c * 13) % 40)}%`,
                }}
              />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}

/** A full-width message row inside a table body (empty states and errors). */
export function TableMessage({
  cols,
  children,
}: {
  cols: number;
  children: React.ReactNode;
}) {
  return (
    <tbody>
      <tr className="pointer-events-none">
        <td colSpan={cols} className="py-12! text-center text-sm opacity-70">
          {children}
        </td>
      </tr>
    </tbody>
  );
}

/**
 * The row's main link. Its hit area stretches over the whole row, so anywhere on the row
 * opens it, while other links or buttons in the row stay clickable on top.
 */
export function RowLink({
  className = "",
  ...props
}: ComponentProps<typeof Link>) {
  return <Link className={`row-link ${className}`} {...props} />;
}
