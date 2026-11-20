"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { PlayerAvatar } from "@/components/players/player-avatar";
import { PositionChip } from "@/components/players/position-chip";
import {
  FilterField,
  PageHeader,
  RowLink,
  SearchInput,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { Button, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import { POSITION_GROUPS, type Page, type PlayerSummary } from "@/lib/types";

const PAGE_SIZE = 15;
const COLS = 5;

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
  const filtered = Object.entries(filters).some(
    ([k, v]) => v !== EMPTY[k as keyof Filters],
  );

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
    placeholderData: (prev) => prev,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Club"
        title="Players"
        meta={
          data
            ? `${data.total} player${data.total === 1 ? "" : "s"} ${filtered ? "match your filters" : "you can see"}`
            : "Everyone in your database, plus players other organizations share."
        }
        actions={
          can("players:write") && (
            <Link href="/players/new" className="btn btn-primary">
              + Add player
            </Link>
          )
        }
      />

      <TableCard
        search={
          <SearchInput
            placeholder="Search by name…"
            value={filters.q}
            onChange={set("q")}
            className="min-w-0 flex-1 sm:min-w-48"
          />
        }
        toolbar={
          <>
            <FilterField label="Position">
              <select
                value={filters.group}
                onChange={set("group")}
                className="field-input capitalize"
              >
                <option value="">All</option>
                {Object.keys(POSITION_GROUPS).map((g) => (
                  <option key={g} value={g}>
                    {g}s
                  </option>
                ))}
              </select>
            </FilterField>
            <FilterField label="Nationality">
              <input
                value={filters.nationality}
                onChange={set("nationality")}
                placeholder="Any"
                className="field-input w-32"
              />
            </FilterField>
            <FilterField label="Age">
              <span className="flex items-center gap-1">
                <input
                  inputMode="numeric"
                  aria-label="Minimum age"
                  placeholder="Min"
                  value={filters.min_age}
                  onChange={set("min_age")}
                  className="field-input w-16"
                />
                <span className="opacity-50">–</span>
                <input
                  inputMode="numeric"
                  aria-label="Maximum age"
                  placeholder="Max"
                  value={filters.max_age}
                  onChange={set("max_age")}
                  className="field-input w-16"
                />
              </span>
            </FilterField>
            <FilterField label="Show">
              <select
                value={filters.scope}
                onChange={set("scope")}
                className="field-input"
              >
                <option value="all">All visible</option>
                <option value="mine">My organization</option>
                <option value="network">Shared by others</option>
              </select>
            </FilterField>
            <FilterField label="Sort">
              <select
                value={filters.sort}
                onChange={set("sort")}
                className="field-input"
              >
                <option value="name">Name</option>
                <option value="age_asc">Youngest first</option>
                <option value="age_desc">Oldest first</option>
                <option value="newest">Recently added</option>
              </select>
            </FilterField>
            {filtered && (
              <Button
                variant="secondary"
                className="h-9"
                onClick={() => (setFilters(EMPTY), setPage(1))}
              >
                Clear filters
              </Button>
            )}
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
              <th>Player</th>
              <th className="num">Age</th>
              <th>Position</th>
              <th className="hidden md:table-cell">Nationality</th>
              <th className="hidden sm:table-cell">Current club</th>
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
              {filtered
                ? "No players match these filters."
                : "No players yet. Add your first player to start building the database."}
            </TableMessage>
          )}
          {data && data.items.length > 0 && (
            <tbody>
              {data.items.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <PlayerAvatar
                        name={p.full_name}
                        src={p.photo_thumb_url}
                        size="sm"
                      />
                      <div className="min-w-0">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <RowLink href={`/players/${p.id}`}>
                            {p.full_name}
                          </RowLink>
                          {p.is_minor && (
                            <span className="chip bg-warn-soft text-warn">
                              U18
                            </span>
                          )}
                          {!p.is_owner && (
                            <span
                              className="chip bg-info-soft text-info"
                              title="Shared with you by another organization"
                            >
                              Shared
                            </span>
                          )}
                        </span>
                        <span className="sub md:hidden">
                          {p.nationality ?? "Nationality unknown"}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="num">{p.age}</td>
                  <td>
                    <PositionChip code={p.primary_position} />
                  </td>
                  <td className="hidden md:table-cell">
                    {p.nationality ?? <span className="opacity-40">—</span>}
                  </td>
                  <td className="hidden sm:table-cell">
                    {p.current_club?.club_name ?? (
                      <span className="opacity-50">No club</span>
                    )}
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
