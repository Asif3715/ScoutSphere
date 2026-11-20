"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/assignments/status-badge";
import { Button, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import {
  PRIORITIES,
  REQUIREMENT_STATUSES,
  label,
  type Page,
  type RequirementSummary,
} from "@/lib/types";

const input =
  "rounded-[2px] border border-line-strong bg-transparent px-3 py-1.5 text-sm";

export default function RecruitmentPage() {
  const { activeOrgId, can } = useAuth();
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

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
  });

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Recruitment</h1>
        <div className="flex gap-2">
          <Link
            href="/recruitment/search"
            className="btn btn-secondary text-sm hover:bg-hover"
          >
            Find players
          </Link>
          {can("recruitment:manage") && (
            <Link href="/recruitment/new" className="btn btn-primary">
              New requirement
            </Link>
          )}
        </div>
      </header>
      <section aria-label="Filters" className="flex flex-wrap items-end gap-3">
        <input
          type="search"
          aria-label="Search requirements"
          placeholder="Search by title…"
          value={q}
          onChange={(e) => (setQ(e.target.value), setPage(1))}
          className={input}
        />
        <label className="text-xs">
          Status
          <select
            value={status}
            onChange={(e) => (setStatus(e.target.value), setPage(1))}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {REQUIREMENT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          Priority
          <select
            value={priority}
            onChange={(e) => (setPriority(e.target.value), setPage(1))}
            className={`${input} block`}
          >
            <option value="">Any</option>
            {PRIORITIES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <Button
          variant="secondary"
          onClick={() => (setStatus(""), setPriority(""), setQ(""), setPage(1))}
        >
          Reset
        </Button>
      </section>

      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && (
        <Empty>
          No requirements yet. A requirement describes the kind of player you
          are looking for.
        </Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase opacity-60">
              <tr>
                <th className="py-2">Requirement</th>
                <th>Position</th>
                <th>Priority</th>
                <th>Candidates</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id} className="border-b border-line-soft">
                  <td className="py-2">
                    <Link
                      href={`/recruitment/${r.id}`}
                      className="font-medium text-link hover:underline"
                    >
                      {r.title}
                    </Link>
                  </td>
                  <td>{r.position}</td>
                  <td>{r.priority}</td>
                  <td>{r.candidate_count}</td>
                  <td>
                    <StatusBadge status={r.status} />
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
