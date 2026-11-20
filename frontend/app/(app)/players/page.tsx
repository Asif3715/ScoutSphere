"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { PlayerAvatar } from "@/components/players/player-avatar";
import { Button, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import { POSITION_GROUPS, type Page, type PlayerSummary } from "@/lib/types";

const PAGE_SIZE = 15;
const input =
  "rounded-[2px] border border-line-strong bg-transparent px-3 py-1.5 text-sm";

type Filters = {
  q: string;
  group: string;
  nationality: string;
  min_age: string;
  max_age: string;
  scope: string;
  sort: string;
};
const EMPTY: Filters = {
  q: "",
  group: "",
  nationality: "",
  min_age: "",
  max_age: "",
  scope: "all",
  sort: "name",
};

export default function PlayersPage() {
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
    queryKey: ["players", activeOrgId, filters, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
      });
      for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
      return apiFetch<Page<PlayerSummary>>(`/players?${params}`);
    },
    enabled: !!activeOrgId,
  });

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Players</h1>
        {can("players:write") && (
          <Link href="/players/new" className="btn btn-primary">
            Add player
          </Link>
        )}
      </header>

      <section aria-label="Filters" className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          <span className="sr-only">Search</span>
          <input
            type="search"
            placeholder="Search by name…"
            value={filters.q}
            onChange={set("q")}
            className={input}
          />
        </label>
        <label className="text-xs">
          Position
          <select
            value={filters.group}
            onChange={set("group")}
            className={`${input} block`}
          >
            <option value="">All</option>
            {Object.keys(POSITION_GROUPS).map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          Nationality
          <input
            value={filters.nationality}
            onChange={set("nationality")}
            className={`${input} block w-32`}
          />
        </label>
        <label className="text-xs">
          Min age
          <input
            inputMode="numeric"
            value={filters.min_age}
            onChange={set("min_age")}
            className={`${input} block w-20`}
          />
        </label>
        <label className="text-xs">
          Max age
          <input
            inputMode="numeric"
            value={filters.max_age}
            onChange={set("max_age")}
            className={`${input} block w-20`}
          />
        </label>
        <label className="text-xs">
          Show
          <select
            value={filters.scope}
            onChange={set("scope")}
            className={`${input} block`}
          >
            <option value="all">All visible</option>
            <option value="mine">My organization</option>
            <option value="network">Shared by others</option>
          </select>
        </label>
        <label className="text-xs">
          Sort
          <select
            value={filters.sort}
            onChange={set("sort")}
            className={`${input} block`}
          >
            <option value="name">Name</option>
            <option value="age_asc">Youngest first</option>
            <option value="age_desc">Oldest first</option>
            <option value="newest">Recently added</option>
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
        <Empty>No players match. Try different filters, or add a player.</Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase opacity-60">
              <tr>
                <th className="py-2">Name</th>
                <th>Age</th>
                <th>Position</th>
                <th>Nationality</th>
                <th>Current club</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.id} className="border-b border-line-soft">
                  <td className="py-2">
                    <PlayerAvatar
                      name={p.full_name}
                      src={p.photo_thumb_url}
                      size="sm"
                      className="mr-2 align-middle"
                    />
                    <Link
                      href={`/players/${p.id}`}
                      className="font-medium text-link hover:underline"
                    >
                      {p.full_name}
                    </Link>
                    {p.is_minor && (
                      <span className="ml-2 rounded bg-warn-soft px-1.5 text-xs text-warn">
                        U18
                      </span>
                    )}
                    {!p.is_owner && (
                      <span className="ml-2 text-xs opacity-50">shared</span>
                    )}
                  </td>
                  <td>{p.age}</td>
                  <td>{p.primary_position ?? "—"}</td>
                  <td>{p.nationality ?? "—"}</td>
                  <td>{p.current_club?.club_name ?? "—"}</td>
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
