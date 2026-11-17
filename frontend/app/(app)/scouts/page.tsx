"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import {
  AGE_GROUPS,
  POSITIONS,
  ROLE_LABELS,
  type Page,
  type Scout,
} from "@/lib/types";

const input =
  "rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm";
type Filters = {
  q: string;
  position: string;
  age_group: string;
  region: string;
  min_experience: string;
  status: string;
};
const EMPTY: Filters = {
  q: "",
  position: "",
  age_group: "",
  region: "",
  min_experience: "",
  status: "active",
};

export default function ScoutsPage() {
  const { activeOrgId, can } = useAuth();
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [page, setPage] = useState(1);
  const set =
    (k: keyof Filters) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setFilters((f) => ({ ...f, [k]: e.target.value }));
      setPage(1);
    };

  const { data, error, isLoading } = useQuery({
    queryKey: ["scouts", activeOrgId, filters, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "12",
      });
      for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
      return apiFetch<Page<Scout>>(`/scouts?${params}`);
    },
    enabled: !!activeOrgId,
  });

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Scouts</h1>
        <Link
          href="/scouts/new"
          className="rounded-md bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
        >
          {can("scouts:manage") ? "Add scout profile" : "Create my profile"}
        </Link>
      </header>

      <section aria-label="Filters" className="flex flex-wrap items-end gap-3">
        <input
          type="search"
          aria-label="Search scouts"
          placeholder="Search by name…"
          value={filters.q}
          onChange={set("q")}
          className={input}
        />
        <label className="text-xs">
          Position
          <select
            value={filters.position}
            onChange={set("position")}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {POSITIONS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          Age group
          <select
            value={filters.age_group}
            onChange={set("age_group")}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {AGE_GROUPS.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          Region
          <input
            value={filters.region}
            onChange={set("region")}
            className={`${input} block w-32`}
          />
        </label>
        <label className="text-xs">
          Min. years
          <input
            inputMode="numeric"
            value={filters.min_experience}
            onChange={set("min_experience")}
            className={`${input} block w-20`}
          />
        </label>
        <label className="text-xs">
          Status
          <select
            value={filters.status}
            onChange={set("status")}
            className={`${input} block`}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="all">All</option>
          </select>
        </label>
        <Button
          variant="secondary"
          onClick={() => (setFilters(EMPTY), setPage(1))}
        >
          Reset
        </Button>
      </section>

      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && (
        <Empty>
          No scout profiles match. Members can create their own profile.
        </Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <ul className="grid gap-3 sm:grid-cols-2" aria-label="Scouts">
            {data.items.map((s) => (
              <li
                key={s.id}
                className="rounded-lg border border-slate-200 p-4 dark:border-slate-800"
              >
                <Link
                  href={`/scouts/${s.id}`}
                  className="font-semibold text-teal-600 hover:underline"
                >
                  {s.full_name}
                </Link>
                {!s.is_active && (
                  <span className="ml-2 rounded bg-slate-200 px-1.5 text-xs text-slate-700">
                    inactive
                  </span>
                )}
                <p className="text-xs opacity-60">
                  {ROLE_LABELS[s.org_role] ?? s.org_role}
                  {s.experience_years != null
                    ? ` · ${s.experience_years} yrs`
                    : ""}
                </p>
                <p className="mt-2 text-sm">
                  {[...s.positions, ...s.age_groups].join(" · ") ||
                    "No specializations yet"}
                </p>
                {s.regions.length > 0 && (
                  <p className="text-xs opacity-70">{s.regions.join(", ")}</p>
                )}
              </li>
            ))}
          </ul>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
