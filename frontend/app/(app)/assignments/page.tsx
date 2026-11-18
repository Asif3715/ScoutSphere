"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/assignments/status-badge";
import { Button, Empty, ErrorText, Pagination, Stat } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import {
  ASSIGNMENT_STATUSES,
  label,
  type AssignmentStats,
  type AssignmentSummary,
  type Page,
} from "@/lib/types";

const input =
  "rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm";

export default function AssignmentsPage() {
  const { activeOrgId, can } = useAuth();
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [page, setPage] = useState(1);

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
  });
  const counts = stats.data?.counts ?? {};
  const open =
    (counts.assigned ?? 0) + (counts.accepted ?? 0) + (counts.in_progress ?? 0);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Assignments</h1>
        {can("assignments:manage") && (
          <Link
            href="/assignments/new"
            className="rounded-md bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
          >
            New assignment
          </Link>
        )}
      </header>

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

      <section aria-label="Filters" className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          Status
          <select
            value={status}
            onChange={(e) => (setStatus(e.target.value), setPage(1))}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {ASSIGNMENT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={overdue}
            onChange={(e) => (setOverdue(e.target.checked), setPage(1))}
          />{" "}
          Overdue only
        </label>
        <Button
          variant="secondary"
          onClick={() => (setStatus(""), setOverdue(false), setPage(1))}
        >
          Reset
        </Button>
      </section>

      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && (
        <Empty>No assignments to show.</Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase opacity-60 dark:border-slate-800">
              <tr>
                <th className="py-2">Assignment</th>
                <th>Target</th>
                <th>Scout</th>
                <th>Deadline</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-slate-100 dark:border-slate-900"
                >
                  <td className="py-2">
                    <Link
                      href={`/assignments/${a.id}`}
                      className="font-medium text-teal-600 hover:underline"
                    >
                      {a.title}
                    </Link>
                  </td>
                  <td>
                    <span className="text-xs opacity-60">
                      {a.target_type}:{" "}
                    </span>
                    {a.target_label}
                  </td>
                  <td>{a.scout_name}</td>
                  <td>
                    {a.deadline ? new Date(a.deadline).toLocaleString() : "—"}
                    {a.is_overdue && (
                      <span className="ml-2 rounded bg-red-100 px-1.5 text-xs text-red-900">
                        overdue
                      </span>
                    )}
                  </td>
                  <td>
                    <StatusBadge status={a.status} />
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
