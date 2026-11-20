"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import type { Club, Page } from "@/lib/types";

const PAGE_SIZE = 10;

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
  });

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Clubs</h1>
        {can("clubs:manage") && (
          <Link href="/clubs/new" className="btn btn-primary">
            Register club
          </Link>
        )}
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" className="flex gap-1">
          {(["mine", "reference"] as const).map((s) => (
            <Button
              key={s}
              role="tab"
              aria-selected={scope === s}
              variant={scope === s ? "primary" : "secondary"}
              onClick={() => {
                setScope(s);
                setPage(1);
              }}
            >
              {s === "mine" ? "My clubs" : "Reference directory"}
            </Button>
          ))}
        </div>
        <label className="sr-only" htmlFor="club-search">
          Search clubs
        </label>
        <input
          id="club-search"
          type="search"
          placeholder="Search by name…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          className="rounded-[2px] border border-line-strong bg-transparent px-3 py-1.5 text-sm"
        />
      </div>

      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && (
        <Empty>
          {scope === "mine"
            ? "No clubs yet. Register your first club to get started."
            : "No reference clubs match."}
        </Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase opacity-60">
              <tr>
                <th className="py-2">Name</th>
                <th>Country</th>
                <th>City</th>
                <th>Founded</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id} className="border-b border-line-soft">
                  <td className="py-2">
                    <Link
                      href={`/clubs/${c.id}`}
                      className="font-medium text-link hover:underline"
                    >
                      {c.name}
                    </Link>
                  </td>
                  <td>{c.country ?? "—"}</td>
                  <td>{c.city ?? "—"}</td>
                  <td>{c.founded_year ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
