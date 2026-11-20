"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/assignments/status-badge";
import {
  FilterField,
  PageHeader,
  RowLink,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { PersonAvatar } from "@/components/ui/person";
import { Button, Pagination, Stat } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { deadlineLabel, shortDateTime } from "@/lib/format";
import { apiFetch } from "@/lib/http";
import {
  ASSIGNMENT_STATUSES,
  label,
  type AssignmentStats,
  type AssignmentSummary,
  type Page,
} from "@/lib/types";

const COLS = 5;
const DONE = new Set(["approved", "rejected", "cancelled"]);
const TONE = {
  bad: "text-bad",
  warn: "text-warn",
  ok: "text-ink",
  muted: "opacity-60",
} as const;

export default function AssignmentsPage() {
  const { activeOrgId, can } = useAuth();
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [page, setPage] = useState(1);
  const filtered = status !== "" || overdue;

  const stats = useQuery({
    queryKey: ["assignment-stats", activeOrgId],
    queryFn: () => apiFetch<AssignmentStats>("/assignments/summary"),
    enabled: !!activeOrgId,
  });
  const { data, error, isLoading } = useQuery({
    queryKey: ["assignments", activeOrgId, status, overdue, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "15",
      });
      if (status) params.set("status", status);
      if (overdue) params.set("overdue", "true");
      return apiFetch<Page<AssignmentSummary>>(`/assignments?${params}`);
    },
    enabled: !!activeOrgId,
    placeholderData: (prev) => prev,
  });
  const counts = stats.data?.counts ?? {};
  const open =
    (counts.assigned ?? 0) + (counts.accepted ?? 0) + (counts.in_progress ?? 0);
  const manage = can("assignments:manage");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Scouting"
        title="Assignments"
        meta={
          manage
            ? "Scouting jobs you've handed out, and where each one stands."
            : "The scouting jobs you've been given."
        }
        actions={
          manage && (
            <Link href="/assignments/new" className="btn btn-primary">
              + New assignment
            </Link>
          )
        }
      />

      <section
        className="grid grid-cols-2 gap-3 sm:grid-cols-4"
        aria-label="Assignment summary"
      >
        <Stat label="Open" value={open} />
        <Stat label="Overdue" value={stats.data?.overdue ?? 0} />
        <Stat label="Due in 48h" value={stats.data?.due_soon ?? 0} />
        <Stat
          label="Awaiting review"
          value={(counts.submitted ?? 0) + (counts.under_review ?? 0)}
        />
      </section>

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
                {ASSIGNMENT_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {label(s)}
                    {counts[s] ? ` (${counts[s]})` : ""}
                  </option>
                ))}
              </select>
            </FilterField>
            <label className="flex h-9 cursor-pointer items-center gap-2 rounded-[2px] border border-line-strong bg-surface px-3 text-sm">
              <input
                type="checkbox"
                checked={overdue}
                onChange={(e) => (setOverdue(e.target.checked), setPage(1))}
              />
              Overdue only
            </label>
            {filtered && (
              <Button
                variant="secondary"
                className="h-9"
                onClick={() => (setStatus(""), setOverdue(false), setPage(1))}
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
              <th>Assignment</th>
              <th className="hidden md:table-cell">Target</th>
              <th className="hidden sm:table-cell">Scout</th>
              <th>Deadline</th>
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
              {filtered
                ? "No assignments match these filters."
                : manage
                  ? "No assignments yet. Create one to send a scout to watch a player or match."
                  : "Nothing assigned to you yet."}
            </TableMessage>
          )}
          {data && data.items.length > 0 && (
            <tbody>
              {data.items.map((a) => {
                const due = deadlineLabel(a.deadline, {
                  done: DONE.has(a.status),
                });
                return (
                  <tr key={a.id}>
                    <td className="max-w-[22rem]">
                      <RowLink href={`/assignments/${a.id}`}>{a.title}</RowLink>
                      <span className="sub">
                        {a.report_count > 0
                          ? `${a.report_count} report${a.report_count === 1 ? "" : "s"}`
                          : "No reports yet"}
                        <span className="md:hidden">
                          {" · "}
                          {a.target_label}
                        </span>
                      </span>
                    </td>
                    <td className="hidden md:table-cell">
                      <span className="chip chip-outline mr-2">
                        {label(a.target_type)}
                      </span>
                      {a.target_label}
                    </td>
                    <td className="hidden sm:table-cell">
                      <span className="flex items-center gap-2 whitespace-nowrap">
                        <PersonAvatar name={a.scout_name} size="xs" />
                        {a.scout_name}
                      </span>
                    </td>
                    <td className="whitespace-nowrap">
                      <span className={`font-medium ${TONE[due.tone]}`}>
                        {due.text}
                      </span>
                      {a.deadline && !DONE.has(a.status) && (
                        <span className="sub">{shortDateTime(a.deadline)}</span>
                      )}
                    </td>
                    <td>
                      <StatusBadge status={a.status} />
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
