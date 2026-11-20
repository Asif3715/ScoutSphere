"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { StatusBadge } from "@/components/assignments/status-badge";
import {
  FilterField,
  PageHeader,
  RowLink,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { Button, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { shortDate } from "@/lib/format";
import { apiFetch } from "@/lib/http";
import {
  label,
  MATCH_STATUSES,
  type MatchSummary,
  type Page,
} from "@/lib/types";

const COLS = 4;

function Fixture({ m }: { m: MatchSummary }) {
  const played = m.home_score != null;
  const homeWon = played && m.home_score! > m.away_score!;
  const awayWon = played && m.away_score! > m.home_score!;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3">
      <span className={`truncate text-right ${homeWon ? "font-semibold" : ""}`}>
        {m.home_club_name}
      </span>
      <RowLink
        href={`/matches/${m.id}`}
        aria-label={`${m.home_club_name} v ${m.away_club_name}`}
        className={`min-w-[4.5rem] rounded-[2px] px-2 py-1 text-center font-mono text-sm tabular-nums ${
          played ? "bg-dugout text-dugout-ink" : "border border-line-strong"
        }`}
      >
        {played ? `${m.home_score} – ${m.away_score}` : "v"}
      </RowLink>
      <span className={`truncate ${awayWon ? "font-semibold" : ""}`}>
        {m.away_club_name}
      </span>
    </div>
  );
}

function Matches() {
  const { activeOrgId, can } = useAuth();
  const seasonId = useSearchParams().get("season_id") ?? "";
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState("kickoff_desc");
  const [page, setPage] = useState(1);
  const filtered = status !== "" || from !== "" || to !== "";

  const { data, error, isLoading } = useQuery({
    queryKey: ["matches", activeOrgId, seasonId, status, from, to, sort, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "15",
        sort,
      });
      if (seasonId) params.set("season_id", seasonId);
      if (status) params.set("status", status);
      if (from) params.set("date_from", from);
      if (to) params.set("date_to", to);
      return apiFetch<Page<MatchSummary>>(`/matches?${params}`);
    },
    enabled: !!activeOrgId,
    placeholderData: (prev) => prev,
  });
  const reset = () => (
    setStatus(""),
    setFrom(""),
    setTo(""),
    setSort("kickoff_desc"),
    setPage(1)
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Fixtures"
        title="Matches"
        meta={
          seasonId ? (
            <>
              Showing one season.{" "}
              <Link href="/matches" className="text-link underline">
                Show all matches
              </Link>
            </>
          ) : (
            "Results and upcoming fixtures across your competitions."
          )
        }
        actions={
          can("matches:manage") && (
            <Link href="/matches/new" className="btn btn-primary">
              + Add match
            </Link>
          )
        }
      />

      <TableCard
        toolbar={
          <>
            <FilterField label="Status">
              <select
                value={status}
                onChange={(e) => (setStatus(e.target.value), setPage(1))}
                className="field-input capitalize"
              >
                <option value="">Any status</option>
                {MATCH_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {label(s)}
                  </option>
                ))}
              </select>
            </FilterField>
            <FilterField label="From">
              <input
                type="date"
                value={from}
                onChange={(e) => (setFrom(e.target.value), setPage(1))}
                className="field-input"
              />
            </FilterField>
            <FilterField label="To">
              <input
                type="date"
                value={to}
                onChange={(e) => (setTo(e.target.value), setPage(1))}
                className="field-input"
              />
            </FilterField>
            <FilterField label="Order">
              <select
                value={sort}
                onChange={(e) => (setSort(e.target.value), setPage(1))}
                className="field-input"
              >
                <option value="kickoff_desc">Newest first</option>
                <option value="kickoff_asc">Oldest first</option>
              </select>
            </FilterField>
            {(filtered || sort !== "kickoff_desc") && (
              <Button variant="secondary" className="h-9" onClick={reset}>
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
              <th className="w-28">Date</th>
              <th className="text-center">Fixture</th>
              <th className="hidden md:table-cell">Competition</th>
              <th>Status</th>
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
              {filtered ? "No matches match these filters." : "No matches yet."}
            </TableMessage>
          )}
          {data && data.items.length > 0 && (
            <tbody>
              {data.items.map((m) => {
                const ko = new Date(m.kickoff_at);
                return (
                  <tr key={m.id}>
                    <td className="whitespace-nowrap">
                      <span className="font-medium">
                        {shortDate(m.kickoff_at)}
                      </span>
                      <span className="sub font-mono">
                        {ko.toLocaleTimeString("en-GB", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                        {m.round_label ? ` · ${m.round_label}` : ""}
                      </span>
                    </td>
                    <td className="min-w-[18rem]">
                      <Fixture m={m} />
                    </td>
                    <td className="hidden md:table-cell">
                      {m.competition_name}
                      <span className="sub">
                        {m.season_name}
                        {m.is_global ? " · global" : ""}
                      </span>
                    </td>
                    <td>
                      <StatusBadge status={m.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          )}
        </table>
      </TableCard>
    </div>
  );
}

export default function MatchesPage() {
  return (
    <Suspense fallback={<p aria-busy="true">Loading…</p>}>
      <Matches />
    </Suspense>
  );
}
