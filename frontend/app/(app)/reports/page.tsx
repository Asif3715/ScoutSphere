"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import {
  RecommendationText,
  StatusBadge,
} from "@/components/assignments/status-badge";
import {
  FilterField,
  PageHeader,
  RowLink,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { PersonAvatar } from "@/components/ui/person";
import { Button, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { shortDate } from "@/lib/format";
import { apiFetch } from "@/lib/http";
import {
  RECOMMENDATIONS,
  REPORT_STATUSES,
  label,
  type Page,
  type ReportSummary,
} from "@/lib/types";

const COLS = 5;

export default function ReportsPage() {
  const { activeOrgId, can } = useAuth();
  const [status, setStatus] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);
  const filtered = status !== "" || recommendation !== "" || mine;

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
    placeholderData: (prev) => prev,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Scouting"
        title="Scouting reports"
        meta={
          data
            ? `${data.total} report${data.total === 1 ? "" : "s"}${filtered ? " match your filters" : ""}`
            : "What your scouts saw, and what they recommend."
        }
        actions={
          can("reports:write") && (
            <Link href="/reports/new" className="btn btn-primary">
              + New report
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
                {REPORT_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {label(s)}
                  </option>
                ))}
              </select>
            </FilterField>
            <FilterField label="Recommendation">
              <select
                value={recommendation}
                onChange={(e) => (
                  setRecommendation(e.target.value),
                  setPage(1)
                )}
                className="field-input capitalize"
              >
                <option value="">Any</option>
                {RECOMMENDATIONS.map((r) => (
                  <option key={r} value={r}>
                    {label(r)}
                  </option>
                ))}
              </select>
            </FilterField>
            {can("reports:write") && (
              <label className="flex h-9 cursor-pointer items-center gap-2 rounded-[2px] border border-line-strong bg-surface px-3 text-sm">
                <input
                  type="checkbox"
                  checked={mine}
                  onChange={(e) => (setMine(e.target.checked), setPage(1))}
                />
                My reports only
              </label>
            )}
            {filtered && (
              <Button
                variant="secondary"
                className="h-9"
                onClick={() => (
                  setStatus(""),
                  setRecommendation(""),
                  setMine(false),
                  setPage(1)
                )}
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
              <th className="hidden sm:table-cell">Scout</th>
              <th className="hidden md:table-cell">Observed</th>
              <th>Verdict</th>
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
              {filtered ? "No reports match these filters." : "No reports yet."}
            </TableMessage>
          )}
          {data && data.items.length > 0 && (
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id}>
                  <td className="max-w-[20rem]">
                    <RowLink href={`/reports/${r.id}`}>{r.player_name}</RowLink>
                    <span className="sub truncate">
                      {r.assignment_title ??
                        r.match_label ??
                        "Standalone report"}
                    </span>
                  </td>
                  <td className="hidden sm:table-cell">
                    <span className="flex items-center gap-2 whitespace-nowrap">
                      <PersonAvatar name={r.scout_name} size="xs" />
                      {r.scout_name}
                    </span>
                  </td>
                  <td className="hidden whitespace-nowrap md:table-cell">
                    {shortDate(r.observed_on)}
                    {r.match_label && (
                      <span className="sub max-w-[14rem] truncate">
                        {r.match_label}
                      </span>
                    )}
                  </td>
                  <td>
                    <RecommendationText value={r.recommendation} />
                  </td>
                  <td className="whitespace-nowrap">
                    <StatusBadge status={r.status} />
                    {r.current_version > 1 && (
                      <span
                        className="ml-1.5 font-mono text-[0.68rem] opacity-60"
                        title={`Version ${r.current_version}`}
                      >
                        v{r.current_version}
                      </span>
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
