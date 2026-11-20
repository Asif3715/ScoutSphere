"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ScoreCell } from "@/components/matches/score";
import { Button, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import { MATCH_STATUSES, type MatchSummary, type Page } from "@/lib/types";

const input =
  "rounded-[2px] border border-line-strong bg-transparent px-3 py-1.5 text-sm";

function Matches() {
  const { activeOrgId, can } = useAuth();
  const seasonId = useSearchParams().get("season_id") ?? "";
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState("kickoff_desc");
  const [page, setPage] = useState(1);

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
  });
  const reset = () => (
    setStatus(""),
    setFrom(""),
    setTo(""),
    setSort("kickoff_desc"),
    setPage(1)
  );

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Matches</h1>
        {can("matches:manage") && (
          <Link href="/matches/new" className="btn btn-primary">
            Add match
          </Link>
        )}
      </header>
      {seasonId && (
        <p className="text-sm">
          Filtered to one season.{" "}
          <Link href="/matches" className="text-link underline">
            Show all matches
          </Link>
        </p>
      )}
      <section aria-label="Filters" className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          Status
          <select
            value={status}
            onChange={(e) => (setStatus(e.target.value), setPage(1))}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {MATCH_STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          From
          <input
            type="date"
            value={from}
            onChange={(e) => (setFrom(e.target.value), setPage(1))}
            className={`${input} block`}
          />
        </label>
        <label className="text-xs">
          To
          <input
            type="date"
            value={to}
            onChange={(e) => (setTo(e.target.value), setPage(1))}
            className={`${input} block`}
          />
        </label>
        <label className="text-xs">
          Order
          <select
            value={sort}
            onChange={(e) => (setSort(e.target.value), setPage(1))}
            className={`${input} block`}
          >
            <option value="kickoff_desc">Newest first</option>
            <option value="kickoff_asc">Oldest first</option>
          </select>
        </label>
        <Button variant="secondary" onClick={reset}>
          Reset
        </Button>
      </section>

      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && <Empty>No matches found.</Empty>}
      {data && data.items.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase opacity-60">
              <tr>
                <th className="py-2">Kick-off</th>
                <th>Match</th>
                <th>Score</th>
                <th>Competition</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((m) => (
                <tr key={m.id} className="border-b border-line-soft">
                  <td className="py-2">
                    {new Date(m.kickoff_at).toLocaleString()}
                  </td>
                  <td>
                    <Link
                      href={`/matches/${m.id}`}
                      className="font-medium text-link hover:underline"
                    >
                      {m.home_club_name} v {m.away_club_name}
                    </Link>
                    {m.is_global && (
                      <span className="ml-2 text-xs opacity-50">global</span>
                    )}
                  </td>
                  <td>
                    <ScoreCell m={m} />
                  </td>
                  <td>
                    {m.competition_name} · {m.season_name}
                  </td>
                  <td>{m.status}</td>
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

export default function MatchesPage() {
  return (
    <Suspense fallback={<p aria-busy="true">Loading…</p>}>
      <Matches />
    </Suspense>
  );
}
