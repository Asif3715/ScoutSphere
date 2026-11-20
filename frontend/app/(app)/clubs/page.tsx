"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import {
  PageHeader,
  RowLink,
  SearchInput,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import { initials } from "@/lib/media";
import type { Club, Page } from "@/lib/types";

const PAGE_SIZE = 10;
const COLS = 3;

export default function ClubsPage() {
  const { activeOrgId, can } = useAuth();
  const [scope, setScope] = useState<"mine" | "reference">("mine");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const { data, error, isLoading } = useQuery({
    queryKey: ["clubs", activeOrgId, scope, q, page],
    queryFn: () =>
      apiFetch<Page<Club>>(
        `/clubs?scope=${scope}&page=${page}&page_size=${PAGE_SIZE}${q ? `&q=${encodeURIComponent(q)}` : ""}`,
      ),
    enabled: !!activeOrgId,
    placeholderData: (prev) => prev,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Club"
        title="Clubs"
        meta="Your own clubs, plus a shared directory of reference clubs."
        actions={
          can("clubs:manage") && (
            <Link href="/clubs/new" className="btn btn-primary">
              + Register club
            </Link>
          )
        }
      />

      <TableCard
        toolbar={
          <>
            <div
              role="tablist"
              aria-label="Which clubs"
              className="flex rounded-[2px] border border-line-strong p-0.5"
            >
              {(["mine", "reference"] as const).map((s) => (
                <button
                  key={s}
                  role="tab"
                  aria-selected={scope === s}
                  onClick={() => (setScope(s), setPage(1))}
                  className={`eyebrow rounded-[1px] px-3 py-2 transition-colors ${
                    scope === s
                      ? "bg-accent text-accent-ink"
                      : "opacity-70 hover:opacity-100"
                  }`}
                >
                  {s === "mine" ? "My clubs" : "Reference directory"}
                </button>
              ))}
            </div>
            <SearchInput
              label="Search clubs"
              placeholder="Search by name…"
              value={q}
              onChange={(e) => (setQ(e.target.value), setPage(1))}
              className="w-full sm:w-64"
            />
          </>
        }
        footer={
          data &&
          data.total > 0 && (
            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              onChange={setPage}
            />
          )
        }
      >
        <table className="data-table">
          <thead>
            <tr>
              <th>Club</th>
              <th>Location</th>
              <th className="num">Founded</th>
            </tr>
          </thead>
          {isLoading && <SkeletonRows cols={COLS} />}
          {error && (
            <TableMessage cols={COLS}>
              <span className="text-bad">{error.message}</span>
            </TableMessage>
          )}
          {data && data.items.length === 0 && (
            <TableMessage cols={COLS}>
              {q
                ? "No clubs match that search."
                : scope === "mine"
                  ? "No clubs yet. Register your first club to get started."
                  : "No reference clubs yet."}
            </TableMessage>
          )}
          {data && data.items.length > 0 && (
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <span
                        aria-hidden="true"
                        className="font-display grid h-9 w-9 shrink-0 place-items-center rounded-[3px] border border-line-strong bg-surface-2 text-sm font-extrabold uppercase"
                      >
                        {c.short_name?.slice(0, 3) ?? initials(c.name)}
                      </span>
                      <div className="min-w-0">
                        <RowLink href={`/clubs/${c.id}`}>{c.name}</RowLink>
                        {c.is_reference && (
                          <span className="sub">Reference club</span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td>
                    {[c.city, c.country].filter(Boolean).join(", ") || (
                      <span className="opacity-40">—</span>
                    )}
                  </td>
                  <td className="num">
                    {c.founded_year ?? <span className="opacity-40">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </TableCard>
    </div>
  );
}
