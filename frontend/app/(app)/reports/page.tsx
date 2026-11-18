"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/assignments/status-badge";
import { Button, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import {
  RECOMMENDATIONS,
  REPORT_STATUSES,
  label,
  type Page,
  type ReportSummary,
} from "@/lib/types";

const input =
  "rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm";

export default function ReportsPage() {
  const { activeOrgId, can } = useAuth();
  const [status, setStatus] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);

  const { data, error, isLoading } = useQuery({
    queryKey: ["reports", activeOrgId, status, recommendation, mine, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "15",
      });
      if (status) params.set("status", status);
      if (recommendation) params.set("recommendation", recommendation);
      if (mine) params.set("mine", "true");
      return apiFetch<Page<ReportSummary>>(`/scouting-reports?${params}`);
    },
    enabled: !!activeOrgId,
  });

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Scouting reports</h1>
        {can("reports:write") && (
          <Link
            href="/reports/new"
            className="rounded-md bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
          >
            New report
          </Link>
        )}
      </header>
      <section aria-label="Filters" className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          Status
          <select
            value={status}
            onChange={(e) => (setStatus(e.target.value), setPage(1))}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {REPORT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          Recommendation
          <select
            value={recommendation}
            onChange={(e) => (setRecommendation(e.target.value), setPage(1))}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {RECOMMENDATIONS.map((r) => (
              <option key={r} value={r}>
                {label(r)}
              </option>
            ))}
          </select>
        </label>
        {can("reports:write") && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={mine}
              onChange={(e) => (setMine(e.target.checked), setPage(1))}
            />{" "}
            My reports only
          </label>
        )}
        <Button
          variant="secondary"
          onClick={() => (
            setStatus(""),
            setRecommendation(""),
            setMine(false),
            setPage(1)
          )}
        >
          Reset
        </Button>
      </section>

      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && <Empty>No reports to show.</Empty>}
      {data && data.items.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase opacity-60 dark:border-slate-800">
              <tr>
                <th className="py-2">Player</th>
                <th>Scout</th>
                <th>Observed</th>
                <th>Match</th>
                <th>Recommendation</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-slate-100 dark:border-slate-900"
                >
                  <td className="py-2">
                    <Link
                      href={`/reports/${r.id}`}
                      className="font-medium text-teal-600 hover:underline"
                    >
                      {r.player_name}
                    </Link>
                  </td>
                  <td>{r.scout_name}</td>
                  <td>{r.observed_on}</td>
                  <td>{r.match_label ?? "—"}</td>
                  <td>{r.recommendation ? label(r.recommendation) : "—"}</td>
                  <td>
                    <StatusBadge status={r.status} />
                    {r.current_version > 1 && (
                      <span className="ml-1 text-xs opacity-60">
                        v{r.current_version}
                      </span>
                    )}
                  </td>
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
