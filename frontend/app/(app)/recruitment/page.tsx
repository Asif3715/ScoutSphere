"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import {
  PriorityBadge,
  StatusBadge,
} from "@/components/assignments/status-badge";
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
import { timeAgo } from "@/lib/format";
import { apiFetch } from "@/lib/http";
import {
  PRIORITIES,
  REQUIREMENT_STATUSES,
  label,
  type Page,
  type RequirementSummary,
} from "@/lib/types";

const COLS = 5;

export default function RecruitmentPage() {
  const { activeOrgId, can } = useAuth();
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const filtered = status !== "" || priority !== "" || q !== "";

  const { data, error, isLoading } = useQuery({
    queryKey: ["requirements", activeOrgId, status, priority, q, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "15",
      });
      if (status) params.set("status", status);
      if (priority) params.set("priority", priority);
      if (q) params.set("q", q);
      return apiFetch<Page<RequirementSummary>>(
        `/recruitment/requirements?${params}`,
      );
    },
    enabled: !!activeOrgId,
    placeholderData: (prev) => prev,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Recruitment"
        title="Pipeline"
        meta="Each requirement describes a player you're looking for, with its candidates."
        actions={
          <>
            <Link href="/recruitment/search" className="btn btn-secondary">
              Find players
            </Link>
            {can("recruitment:manage") && (
              <Link href="/recruitment/new" className="btn btn-primary">
                + New requirement
              </Link>
            )}
          </>
        }
      />

      <TableCard
        search={
          <SearchInput
            label="Search requirements"
            placeholder="Search by title…"
            value={q}
            onChange={(e) => (setQ(e.target.value), setPage(1))}
            className="min-w-0 flex-1 sm:max-w-64"
          />
        }
        toolbar={
          <>
            <FilterField label="Status">
              <select
                value={status}
                onChange={(e) => (setStatus(e.target.value), setPage(1))}
                className="field-input capitalize"
              >
                <option value="">Any status</option>
                {REQUIREMENT_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {label(s)}
                  </option>
                ))}
              </select>
            </FilterField>
            <FilterField label="Priority">
              <select
                value={priority}
                onChange={(e) => (setPriority(e.target.value), setPage(1))}
                className="field-input capitalize"
              >
                <option value="">Any</option>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </FilterField>
            {filtered && (
              <Button
                variant="secondary"
                className="h-9"
                onClick={() => (
                  setStatus(""),
                  setPriority(""),
                  setQ(""),
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
              <th>Requirement</th>
              <th>Position</th>
              <th className="hidden sm:table-cell">Priority</th>
              <th className="num">Candidates</th>
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
                ? "No requirements match these filters."
                : "No requirements yet. A requirement describes the kind of player you are looking for."}
            </TableMessage>
          )}
          {data && data.items.length > 0 && (
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <RowLink href={`/recruitment/${r.id}`}>{r.title}</RowLink>
                    <span className="sub">Opened {timeAgo(r.created_at)}</span>
                  </td>
                  <td>
                    <PositionChip code={r.position} />
                  </td>
                  <td className="hidden sm:table-cell">
                    <PriorityBadge priority={r.priority} />
                  </td>
                  <td className="num">
                    <span
                      className={r.candidate_count === 0 ? "opacity-40" : ""}
                    >
                      {r.candidate_count}
                    </span>
                  </td>
                  <td>
                    <StatusBadge status={r.status} />
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
