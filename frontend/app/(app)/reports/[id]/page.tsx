"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { StatusBadge } from "@/components/assignments/status-badge";
import { ReportEditor } from "@/components/reports/report-editor";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import {
  missingForSubmit,
  reportPayload,
  reviewSchema,
  type ReviewValues,
} from "@/lib/schemas";
import { RATING_GROUPS, label, type ReportDetail } from "@/lib/types";

type Snapshot = Record<string, unknown> & {
  version: number;
  ratings: Record<string, number>;
};

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState<number | null>(null);

  const {
    data: r,
    error: loadError,
    isLoading,
  } = useQuery({
    queryKey: ["report", activeOrgId, id],
    queryFn: () => apiFetch<ReportDetail>(`/scouting-reports/${id}`),
    enabled: !!activeOrgId,
  });
  const snapshot = useQuery({
    queryKey: ["report-version", activeOrgId, id, version],
    queryFn: () =>
      apiFetch<Snapshot>(`/scouting-reports/${id}/versions/${version}`),
    enabled: !!activeOrgId && version !== null,
  });
  const review = useForm<ReviewValues>({
    resolver: zodResolver(reviewSchema),
    defaultValues: { decision: "approved" },
  });

  if (isLoading) return <p aria-busy="true">Loading…</p>;
  if (loadError || !r) {
    return (
      <div className="space-y-2">
        <ErrorText>{loadError?.message ?? "Report not found"}</ErrorText>
        <Link href="/reports" className="text-sm text-teal-600 underline">
          Back to reports
        </Link>
      </div>
    );
  }

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["report", activeOrgId, id] });
    await qc.invalidateQueries({ queryKey: ["reports"] });
    await qc.invalidateQueries({ queryKey: ["assignment"] });
    await qc.invalidateQueries({ queryKey: ["notifications"] });
  };
  const fail = (e: unknown) =>
    setError(e instanceof ApiError ? e.message : "Request failed");
  const missing = missingForSubmit(r);

  async function submitReport() {
    setError(null);
    try {
      await apiFetch(`/scouting-reports/${id}/submit`, { method: "POST" });
      await refresh();
    } catch (e) {
      fail(e);
    }
  }
  async function deleteDraft() {
    if (!window.confirm("Delete this draft?")) return;
    try {
      await apiFetch(`/scouting-reports/${id}`, { method: "DELETE" });
      await qc.invalidateQueries({ queryKey: ["reports"] });
      router.replace("/reports");
    } catch (e) {
      fail(e);
    }
  }
  const sendReview = review.handleSubmit(async (v) => {
    setError(null);
    try {
      await apiFetch(`/scouting-reports/${id}/review`, {
        method: "POST",
        json: { decision: v.decision, comment: v.comment?.trim() || null },
      });
      review.reset({ decision: "approved", comment: "" });
      await refresh();
    } catch (e) {
      fail(e);
    }
  });

  const shown = version !== null && snapshot.data ? snapshot.data : null;
  const ratings = shown ? shown.ratings : r.ratings;
  const text = (
    k:
      "strengths" | "weaknesses" | "development_areas" | "general_observations",
  ) => (shown ? (shown[k] as string | null) : r[k]) ?? null;

  return (
    <div className="space-y-6">
      <Link href="/reports" className="text-sm text-teal-600 underline">
        ← Reports
      </Link>
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">
          {r.player_name} <StatusBadge status={r.status} />
        </h1>
        <p className="text-sm opacity-70">
          By {r.scout_name} · observed {r.observed_on}
          {r.match_label ? ` · ${r.match_label}` : ""}
          {r.position_observed ? ` · as ${r.position_observed}` : ""}
          {r.current_version > 0
            ? ` · version ${r.current_version}`
            : " · never submitted"}
        </p>
        {r.assignment_id && (
          <p className="text-sm">
            Assignment:{" "}
            <Link
              href={`/assignments/${r.assignment_id}`}
              className="text-teal-600 underline"
            >
              {r.assignment_title}
            </Link>
          </p>
        )}
      </header>
      <ErrorText>{error}</ErrorText>

      {r.status === "revision_requested" && r.reviews.length > 0 && (
        <Card className="border-amber-400 bg-amber-50 text-sm text-amber-950">
          <p className="font-semibold">Revision requested</p>
          <p>{r.reviews[r.reviews.length - 1].comment}</p>
        </Card>
      )}

      {r.can_edit && !editing && (
        <Card className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Edit report
            </Button>
            <Button onClick={submitReport} disabled={missing.length > 0}>
              {r.current_version === 0
                ? "Submit for review"
                : "Resubmit for review"}
            </Button>
            {r.current_version === 0 && (
              <Button variant="danger" onClick={deleteDraft}>
                Delete draft
              </Button>
            )}
          </div>
          {missing.length > 0 && (
            <p className="text-xs text-amber-700">
              Before submitting, add: {missing.join(", ")}.
            </p>
          )}
        </Card>
      )}

      {editing ? (
        <ReportEditor
          report={r}
          submitLabel="Save changes"
          onSubmit={async (values) => {
            const base = reportPayload(values);
            // blank ratings that existed before must be sent as null to remove them
            const ratings: Record<string, number | null> = { ...base.ratings };
            for (const a of Object.keys(r.ratings))
              if (!(a in base.ratings)) ratings[a] = null;
            await apiFetch(`/scouting-reports/${id}`, {
              method: "PATCH",
              json: { ...base, ratings },
            });
            await refresh();
            setEditing(false);
          }}
        />
      ) : (
        <>
          {r.versions.length > 0 && (
            <label className="text-sm">
              Viewing{" "}
              <select
                aria-label="Report version"
                value={version ?? ""}
                onChange={(e) =>
                  setVersion(e.target.value ? Number(e.target.value) : null)
                }
                className="rounded-md border border-slate-300 bg-transparent px-2 py-1"
              >
                <option value="">current</option>
                {r.versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    version {v.version} (
                    {new Date(v.created_at).toLocaleDateString()})
                  </option>
                ))}
              </select>
            </label>
          )}
          <section className="grid gap-4 sm:grid-cols-2" aria-label="Ratings">
            {Object.entries(RATING_GROUPS).map(([group, attrs]) => (
              <Card key={group} className="space-y-1 text-sm">
                <h3 className="font-semibold capitalize">{group}</h3>
                {attrs.map((a) => (
                  <div key={a} className="flex justify-between">
                    <span className="capitalize">{label(a)}</span>
                    <strong>{ratings[a] ?? "—"}</strong>
                  </div>
                ))}
              </Card>
            ))}
          </section>
          <Card className="space-y-3 text-sm">
            {(
              [
                ["strengths", "Strengths"],
                ["weaknesses", "Weaknesses"],
                ["development_areas", "Development areas"],
                ["general_observations", "General observations"],
              ] as const
            ).map(([k, title]) => (
              <div key={k}>
                <p className="text-xs uppercase opacity-60">{title}</p>
                <p className="whitespace-pre-wrap">{text(k) || "—"}</p>
              </div>
            ))}
            <p>
              <span className="text-xs uppercase opacity-60">
                Recommendation:{" "}
              </span>
              <strong>
                {(
                  shown
                    ? (shown.recommendation as string | null)
                    : r.recommendation
                )
                  ? label(
                      (shown
                        ? (shown.recommendation as string)
                        : r.recommendation)!,
                    )
                  : "—"}
              </strong>
            </p>
          </Card>
        </>
      )}

      {r.can_review && (
        <Card className="space-y-3">
          <h2 className="font-semibold">Review this report</h2>
          <form
            method="post"
            onSubmit={sendReview}
            className="space-y-3"
            noValidate
          >
            <div className="space-y-1 text-sm">
              {(["approved", "revision_requested", "rejected"] as const).map(
                (d) => (
                  <label
                    key={d}
                    className="mr-4 inline-flex items-center gap-1"
                  >
                    <input
                      type="radio"
                      value={d}
                      {...review.register("decision")}
                    />{" "}
                    {label(d)}
                  </label>
                ),
              )}
            </div>
            <label className="block text-sm">
              Comment (required unless approving)
              <textarea
                rows={3}
                className="mt-1 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm"
                {...review.register("comment")}
              />
            </label>
            <ErrorText>{review.formState.errors.comment?.message}</ErrorText>
            <Button type="submit" disabled={review.formState.isSubmitting}>
              Submit review
            </Button>
          </form>
        </Card>
      )}

      {r.reviews.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Review history</h2>
          <ul className="space-y-1 text-sm">
            {r.reviews.map((rv, i) => (
              <li
                key={i}
                className="rounded-md border border-slate-200 px-3 py-1.5 dark:border-slate-800"
              >
                <strong>{label(rv.decision)}</strong> on v{rv.version} by{" "}
                {rv.reviewer_name ?? "unknown"}{" "}
                <span className="text-xs opacity-60">
                  {new Date(rv.created_at).toLocaleString()}
                </span>
                {rv.comment && (
                  <p className="text-xs opacity-80">“{rv.comment}”</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
