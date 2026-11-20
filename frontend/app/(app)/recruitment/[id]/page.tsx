"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { StatusBadge } from "@/components/assignments/status-badge";
import { RequirementForm } from "@/components/recruitment/requirement-form";
import { Button, Card, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { allowedStages } from "@/lib/stages";
import {
  STAGE_ORDER,
  label,
  type Candidate,
  type CandidateDetail,
  type CandidateMatch,
  type Page,
  type Requirement,
  type Scout,
} from "@/lib/types";

const input =
  "rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm";

export default function RequirementPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId, can } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"pipeline" | "find">("pipeline");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const req = useQuery({
    queryKey: ["requirement", activeOrgId, id],
    queryFn: () => apiFetch<Requirement>(`/recruitment/requirements/${id}`),
    enabled: !!activeOrgId,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["requirement", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["candidates", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["matches", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["requirements"] });
  };
  const fail = (e: unknown) =>
    setError(e instanceof ApiError ? e.message : "Request failed");

  if (req.isLoading) return <p aria-busy="true">Loading…</p>;
  if (req.error || !req.data) {
    return (
      <div className="space-y-2">
        <ErrorText>{req.error?.message ?? "Requirement not found"}</ErrorText>
        <Link href="/recruitment" className="text-sm text-teal-600 underline">
          Back to recruitment
        </Link>
      </div>
    );
  }
  const r = req.data;
  const manage = can("recruitment:manage");
  const closed = r.status === "fulfilled" || r.status === "cancelled";

  async function setStatus(status: string) {
    setError(null);
    try {
      await apiFetch(`/recruitment/requirements/${id}`, {
        method: "PATCH",
        json: { status },
      });
      refresh();
    } catch (e) {
      fail(e);
    }
  }

  const criteria: [string, string][] = [
    ["Position", r.position],
    [
      "Age",
      r.min_age || r.max_age
        ? `${r.min_age ?? "…"}–${r.max_age ?? "…"}`
        : "any",
    ],
    ["Nationality", r.nationality ?? "any"],
    ["Preferred foot", r.preferred_foot ?? "any"],
    [
      "Career appearances",
      r.min_appearances ? `≥ ${r.min_appearances}` : "any",
    ],
    ...Object.entries(r.attributes).map(
      ([a, m]) => [`${label(a)} rating`, `≥ ${m}`] as [string, string],
    ),
  ];

  return (
    <div className="space-y-5">
      <Link href="/recruitment" className="text-sm text-teal-600 underline">
        ← Recruitment
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">
            {r.title} <StatusBadge status={r.status} />
          </h1>
          <p className="text-sm opacity-70">
            {r.position} · priority {r.priority}
            {r.created_by_name ? ` · created by ${r.created_by_name}` : ""}
          </p>
        </div>
        {manage && !editing && (
          <div className="flex flex-wrap gap-2">
            {r.allowed_statuses.map((s) => (
              <Button
                key={s}
                variant={s === "cancelled" ? "danger" : "secondary"}
                onClick={() => setStatus(s)}
              >
                Mark {label(s)}
              </Button>
            ))}
            {!closed && (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
          </div>
        )}
      </header>
      <ErrorText>{error}</ErrorText>

      {editing ? (
        <RequirementForm
          requirement={r}
          submitLabel="Save changes"
          onSubmit={async (payload) => {
            await apiFetch(`/recruitment/requirements/${id}`, {
              method: "PATCH",
              json: payload,
            });
            refresh();
            setEditing(false);
          }}
        />
      ) : (
        <Card className="space-y-3 text-sm">
          <p className="text-xs uppercase opacity-60">
            What we are looking for
          </p>
          <ul className="flex flex-wrap gap-2" aria-label="Criteria">
            {criteria.map(([k, v]) => (
              <li
                key={k}
                className="rounded-full border border-slate-300 px-3 py-0.5"
              >
                <span className="opacity-60">{k}:</span> {v}
              </li>
            ))}
          </ul>
          {(r.budget_min != null || r.budget_max != null) && (
            <p>
              Budget: {r.budget_min?.toLocaleString() ?? "…"} –{" "}
              {r.budget_max?.toLocaleString() ?? "…"} {r.currency}{" "}
              <span className="text-xs opacity-60">
                (for reference; not used for matching)
              </span>
            </p>
          )}
          {r.contract_notes && (
            <p className="whitespace-pre-wrap">Contract: {r.contract_notes}</p>
          )}
          {r.instructions && (
            <p className="whitespace-pre-wrap">{r.instructions}</p>
          )}
        </Card>
      )}

      <div role="tablist" className="flex gap-2">
        {(
          [
            ["pipeline", `Pipeline (${r.candidate_count})`],
            ["find", "Find candidates"],
          ] as const
        ).map(([key, text]) => (
          <Button
            key={key}
            role="tab"
            aria-selected={tab === key}
            variant={tab === key ? "primary" : "secondary"}
            onClick={() => setTab(key)}
          >
            {text}
          </Button>
        ))}
      </div>

      {tab === "pipeline" ? (
        <Pipeline
          requirementId={id}
          closed={closed}
          manage={manage}
          onChange={refresh}
          onError={setError}
        />
      ) : (
        <Discovery
          requirementId={id}
          closed={closed}
          manage={manage}
          onChange={refresh}
          onError={setError}
        />
      )}
    </div>
  );
}

function Pipeline({
  requirementId,
  closed,
  manage,
  onChange,
  onError,
}: {
  requirementId: string;
  closed: boolean;
  manage: boolean;
  onChange: () => void;
  onError: (m: string | null) => void;
}) {
  const { activeOrgId, can } = useAuth();
  const list = useQuery({
    queryKey: ["candidates", activeOrgId, requirementId],
    queryFn: () =>
      apiFetch<Page<Candidate>>(
        `/recruitment/requirements/${requirementId}/candidates?page_size=100`,
      ),
    enabled: !!activeOrgId,
  });
  if (list.isLoading) return <p aria-busy="true">Loading…</p>;
  const items = list.data?.items ?? [];
  if (items.length === 0)
    return (
      <Empty>No candidates yet. Use “Find candidates” to add players.</Empty>
    );
  const stages = [...STAGE_ORDER, "rejected", "archived"] as string[];
  return (
    <div className="space-y-4">
      {stages
        .filter((s) => items.some((c) => c.stage === s))
        .map((stage) => (
          <section key={stage} className="space-y-2" aria-label={label(stage)}>
            <h2 className="text-sm font-semibold uppercase opacity-70">
              {label(stage)} ({items.filter((c) => c.stage === stage).length})
            </h2>
            <ul className="space-y-2">
              {items
                .filter((c) => c.stage === stage)
                .map((c) => (
                  <CandidateRow
                    key={c.id}
                    c={c}
                    manage={manage}
                    canAssign={can("assignments:manage")}
                    closed={closed}
                    onChange={onChange}
                    onError={onError}
                  />
                ))}
            </ul>
          </section>
        ))}
    </div>
  );
}

function CandidateRow({
  c,
  manage,
  canAssign,
  closed,
  onChange,
  onError,
}: {
  c: Candidate;
  manage: boolean;
  canAssign: boolean;
  closed: boolean;
  onChange: () => void;
  onError: (m: string | null) => void;
}) {
  const { activeOrgId } = useAuth();
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [scoutId, setScoutId] = useState("");
  const detail = useQuery({
    queryKey: ["candidate", activeOrgId, c.id, c.stage],
    queryFn: () => apiFetch<CandidateDetail>(`/recruitment/candidates/${c.id}`),
    enabled: open,
  });
  const scouts = useQuery({
    queryKey: ["scouts", activeOrgId, "options"],
    queryFn: () => apiFetch<Page<Scout>>("/scouts?page_size=100"),
    enabled: assigning,
  });

  async function run(fn: () => Promise<unknown>) {
    onError(null);
    try {
      await fn();
      setTo("");
      setNote("");
      setAssigning(false);
      onChange();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Request failed");
    }
  }
  const moves = allowedStages(c.stage);

  return (
    <li className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <Link
            href={`/players/${c.player_id}`}
            className="font-medium text-teal-600 hover:underline"
          >
            {c.player_name}
          </Link>{" "}
          <span className="opacity-60">
            {c.age} · {c.primary_position ?? "—"}
          </span>
          {c.assignment_id && (
            <Link
              href={`/assignments/${c.assignment_id}`}
              className="ml-2 text-xs text-teal-600 underline"
            >
              assignment:{" "}
              {c.assignment_status ? label(c.assignment_status) : "view"}
            </Link>
          )}
          {c.notes && <p className="text-xs opacity-70">{c.notes}</p>}
        </div>
        <Button
          variant="secondary"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          {open ? "Hide history" : "History"}
        </Button>
      </div>

      {manage && moves.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <select
            aria-label={`Move ${c.player_name} to`}
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className={input}
          >
            <option value="">Move to…</option>
            {moves.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
          <input
            aria-label="Note"
            placeholder="Note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className={`${input} flex-1`}
          />
          <Button
            variant="secondary"
            disabled={!to}
            onClick={() =>
              run(() =>
                apiFetch(`/recruitment/candidates/${c.id}/stage`, {
                  method: "POST",
                  json: { to, note: note || null },
                }),
              )
            }
          >
            Move
          </Button>
          {canAssign &&
            !closed &&
            !["rejected", "archived", "signed"].includes(c.stage) && (
              <Button
                variant="secondary"
                onClick={() => setAssigning((a) => !a)}
              >
                Assign scout
              </Button>
            )}
        </div>
      )}

      {assigning && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <select
            aria-label="Scout"
            value={scoutId}
            onChange={(e) => setScoutId(e.target.value)}
            className={input}
          >
            <option value="">Choose a scout…</option>
            {scouts.data?.items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.full_name}
              </option>
            ))}
          </select>
          <Button
            disabled={!scoutId}
            onClick={() =>
              run(() =>
                apiFetch(`/recruitment/candidates/${c.id}/assign-scout`, {
                  method: "POST",
                  json: { scout_id: scoutId },
                }),
              )
            }
          >
            Send assignment
          </Button>
        </div>
      )}

      {open && (
        <ol className="mt-3 space-y-1 border-t border-slate-200 pt-2 text-xs dark:border-slate-800">
          {detail.data?.history.map((h, i) => (
            <li key={i}>
              <span className="opacity-60">
                {new Date(h.created_at).toLocaleString()}
              </span>{" "}
              {h.from_stage ? `${label(h.from_stage)} → ` : ""}
              <strong>{label(h.to_stage)}</strong>{" "}
              {h.actor_name && (
                <span className="opacity-70">by {h.actor_name}</span>
              )}
              {h.note && <span className="opacity-80"> — “{h.note}”</span>}
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}

function Discovery({
  requirementId,
  closed,
  manage,
  onChange,
  onError,
}: {
  requirementId: string;
  closed: boolean;
  manage: boolean;
  onChange: () => void;
  onError: (m: string | null) => void;
}) {
  const { activeOrgId } = useAuth();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const matches = useQuery({
    queryKey: ["matches", activeOrgId, requirementId, page],
    queryFn: () =>
      apiFetch<Page<CandidateMatch>>(
        `/recruitment/requirements/${requirementId}/matches?page=${page}&page_size=10`,
      ),
    enabled: !!activeOrgId,
  });

  async function add(ids: string[]) {
    onError(null);
    try {
      await apiFetch(
        `/recruitment/requirements/${requirementId}/candidates/bulk`,
        { method: "POST", json: { player_ids: ids } },
      );
      setSelected([]);
      onChange();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Request failed");
    }
  }

  if (matches.isLoading) return <p aria-busy="true">Searching…</p>;
  const data = matches.data;
  return (
    <div className="space-y-3">
      <p className="text-xs opacity-60">
        Players you can see who meet <strong>every</strong> criterion. Ratings
        are averages over your own approved scouting reports.
      </p>
      <ErrorText>{matches.error?.message}</ErrorText>
      {data && data.items.length === 0 && (
        <Empty>
          No players match every criterion yet, or they are all in the pipeline
          already.
        </Empty>
      )}
      {manage && !closed && selected.length > 0 && (
        <Button onClick={() => add(selected)}>
          Add {selected.length} selected to pipeline
        </Button>
      )}
      <ul className="space-y-2">
        {data?.items.map((m) => (
          <li
            key={m.player.id}
            className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2">
                {manage && !closed && (
                  <input
                    type="checkbox"
                    aria-label={`Select ${m.player.full_name}`}
                    className="mt-1"
                    checked={selected.includes(m.player.id)}
                    onChange={(e) =>
                      setSelected((s) =>
                        e.target.checked
                          ? [...s, m.player.id]
                          : s.filter((x) => x !== m.player.id),
                      )
                    }
                  />
                )}
                <div>
                  <Link
                    href={`/players/${m.player.id}`}
                    className="font-medium text-teal-600 hover:underline"
                  >
                    {m.player.full_name}
                  </Link>{" "}
                  <span className="opacity-60">
                    {m.player.age} · {m.player.primary_position ?? "—"} ·{" "}
                    {m.player.current_club?.club_name ?? "no club"}
                  </span>
                  <ul
                    className="mt-1 flex flex-wrap gap-1.5 text-xs"
                    aria-label="Criteria breakdown"
                  >
                    {m.criteria.map((c) => (
                      <li
                        key={c.name}
                        className={`rounded px-1.5 py-0.5 ${c.met ? "bg-green-100 text-green-900" : "bg-red-100 text-red-900"}`}
                      >
                        {c.met ? "✓" : "✗"} {c.name}: {c.actual ?? "no data"}{" "}
                        <span className="opacity-60">(need {c.required})</span>
                      </li>
                    ))}
                  </ul>
                  {m.report_count > 0 && (
                    <p className="mt-1 text-xs opacity-60">
                      Based on {m.report_count} approved report
                      {m.report_count === 1 ? "" : "s"}
                    </p>
                  )}
                </div>
              </div>
              {manage && !closed && (
                <Button variant="secondary" onClick={() => add([m.player.id])}>
                  Add
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      {data && (
        <Pagination
          page={data.page}
          pageSize={data.page_size}
          total={data.total}
          onChange={setPage}
        />
      )}
    </div>
  );
}
