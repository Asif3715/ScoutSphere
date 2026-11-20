"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { StatusBadge } from "@/components/assignments/status-badge";
import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { label, type AssignmentDetail } from "@/lib/types";

const TRANSITION_LABELS: Record<string, string> = {
  assigned: "Send to scout",
  accepted: "Accept assignment",
  in_progress: "Start work",
  submitted: "Submit for review",
  under_review: "Start review",
  approved: "Approve",
  rejected: "Reject",
  cancelled: "Cancel assignment",
};

export default function AssignmentPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId } = useAuth();
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const {
    data: a,
    error: loadError,
    isLoading,
  } = useQuery({
    queryKey: ["assignment", activeOrgId, id],
    queryFn: () => apiFetch<AssignmentDetail>(`/assignments/${id}`),
    enabled: !!activeOrgId,
  });

  if (isLoading) return <p aria-busy="true">Loading…</p>;
  if (loadError || !a) {
    return (
      <div className="space-y-2">
        <ErrorText>{loadError?.message ?? "Assignment not found"}</ErrorText>
        <Link href="/assignments" className="text-sm text-link underline">
          Back to assignments
        </Link>
      </div>
    );
  }

  async function move(to: string) {
    setError(null);
    setBusy(true);
    try {
      await apiFetch(`/assignments/${id}/transition`, {
        method: "POST",
        json: { to, note: note.trim() || null },
      });
      setNote("");
      await qc.invalidateQueries({ queryKey: ["assignment", activeOrgId, id] });
      await qc.invalidateQueries({ queryKey: ["assignments"] });
      await qc.invalidateQueries({ queryKey: ["assignment-stats"] });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  const canWriteReport =
    a.is_mine && ["accepted", "in_progress"].includes(a.status);
  const targetHref =
    a.target_type === "match"
      ? `/matches/${a.target_id}`
      : a.target_type === "player"
        ? `/players/${a.target_id}`
        : `/competitions/${a.target_id}`;
  const newReportHref = `/reports/new?assignment_id=${a.id}${a.target_type === "player" ? `&player_id=${a.target_id}` : ""}${
    a.target_type === "match" ? `&match_id=${a.target_id}` : ""
  }`;

  return (
    <div className="space-y-6">
      <Link href="/assignments" className="text-sm text-link underline">
        ← Assignments
      </Link>
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">
          {a.title} <StatusBadge status={a.status} />
        </h1>
        <p className="text-sm opacity-70">
          {a.target_type}:{" "}
          <Link href={targetHref} className="text-link underline">
            {a.target_label}
          </Link>{" "}
          · Scout: {a.scout_name}
        </p>
        <p className="text-sm">
          Deadline:{" "}
          {a.deadline ? new Date(a.deadline).toLocaleString() : "none"}
          {a.is_overdue && (
            <span className="ml-2 rounded bg-bad-soft px-1.5 text-xs text-bad">
              overdue
            </span>
          )}
        </p>
      </header>
      <ErrorText>{error}</ErrorText>

      {(a.instructions || a.criteria) && (
        <Card className="space-y-3 text-sm">
          {a.instructions && (
            <div>
              <p className="text-xs uppercase opacity-60">Instructions</p>
              <p className="whitespace-pre-wrap">{a.instructions}</p>
            </div>
          )}
          {a.criteria && (
            <div>
              <p className="text-xs uppercase opacity-60">
                Evaluation criteria
              </p>
              <p className="whitespace-pre-wrap">{a.criteria}</p>
            </div>
          )}
        </Card>
      )}

      {a.allowed_transitions.length > 0 && (
        <Card className="space-y-3">
          <h2 className="font-semibold">Next steps</h2>
          <label className="block text-sm">
            Note (required when returning or rejecting submitted work)
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {a.allowed_transitions.map((to) => {
              const returning =
                to === "in_progress" &&
                ["submitted", "under_review"].includes(a.status);
              return (
                <Button
                  key={to}
                  variant={
                    to === "cancelled" || to === "rejected"
                      ? "danger"
                      : to === "approved" || to === "accepted"
                        ? "primary"
                        : "secondary"
                  }
                  disabled={busy}
                  onClick={() => move(to)}
                >
                  {returning
                    ? "Return for changes"
                    : (TRANSITION_LABELS[to] ?? label(to))}
                </Button>
              );
            })}
          </div>
        </Card>
      )}

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Reports ({a.reports.length})
          </h2>
          {canWriteReport && (
            <Link href={newReportHref} className="btn btn-primary">
              Write report
            </Link>
          )}
        </div>
        {a.reports.length === 0 ? (
          <Empty>No reports yet.</Empty>
        ) : (
          <ul className="space-y-2">
            {a.reports.map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between rounded-[2px] border border-line px-3 py-2 text-sm"
              >
                <Link
                  href={`/reports/${r.id}`}
                  className="font-medium text-link hover:underline"
                >
                  {r.player_name}
                </Link>
                <span>
                  {r.recommendation ? `${label(r.recommendation)} · ` : ""}
                  <StatusBadge status={r.status} />
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">History</h2>
        <ol className="space-y-1 text-sm">
          {a.history.map((h, i) => (
            <li
              key={i}
              className="rounded-[2px] border border-line px-3 py-1.5"
            >
              <span className="text-xs opacity-60">
                {new Date(h.created_at).toLocaleString()}
              </span>{" "}
              {h.from_status && h.from_status !== h.to_status ? (
                <>
                  {label(h.from_status)} → <strong>{label(h.to_status)}</strong>
                </>
              ) : (
                <strong>{label(h.to_status)}</strong>
              )}{" "}
              {h.actor_name && (
                <span className="opacity-70">by {h.actor_name}</span>
              )}
              {h.note && <p className="text-xs opacity-80">“{h.note}”</p>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
