"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ScoreCell } from "@/components/matches/score";
import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { eventSchema, statsSideSchema, type EventValues } from "@/lib/schemas";
import {
  EVENT_TYPES,
  MATCH_TRANSITIONS,
  STAT_FIELDS,
  type MatchDetail,
  type StatsSide,
} from "@/lib/types";

const input =
  "rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm";

export default function MatchPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId } = useAuth();
  const qc = useQueryClient();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const {
    data: m,
    error: loadError,
    isLoading,
  } = useQuery({
    queryKey: ["match", activeOrgId, id],
    queryFn: () => apiFetch<MatchDetail>(`/matches/${id}`),
    enabled: !!activeOrgId,
  });

  if (isLoading) return <p aria-busy="true">Loading…</p>;
  if (loadError || !m) {
    return (
      <div className="space-y-2">
        <ErrorText>{loadError?.message ?? "Match not found"}</ErrorText>
        <Link href="/matches" className="text-sm text-teal-600 underline">
          Back to matches
        </Link>
      </div>
    );
  }
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["match", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["matches"] });
  };
  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Request failed");
    }
  }
  const started = m.status === "live" || m.status === "finished";
  const patch = (json: object) =>
    run(() => apiFetch(`/matches/${id}`, { method: "PATCH", json }));

  return (
    <div className="space-y-6">
      <Link href="/matches" className="text-sm text-teal-600 underline">
        ← Matches
      </Link>
      <header className="space-y-1">
        <p className="text-sm opacity-70">
          {m.competition_name} · {m.season_name}
          {m.round_label ? ` · ${m.round_label}` : ""}{" "}
          {m.is_global && "· Global (read-only)"}
        </p>
        <h1 className="text-2xl font-bold">
          {m.home_club_name}{" "}
          <span className="mx-2 text-3xl">
            {m.home_score == null ? "v" : <ScoreCell m={m} />}
          </span>{" "}
          {m.away_club_name}
        </h1>
        <p className="text-sm opacity-70">
          {new Date(m.kickoff_at).toLocaleString()}
          {m.venue ? ` · ${m.venue}` : ""} · <strong>{m.status}</strong>
        </p>
      </header>
      <ErrorText>{error}</ErrorText>

      {m.editable && (
        <Card className="space-y-3">
          <h2 className="font-semibold">Manage match</h2>
          <div className="flex flex-wrap items-center gap-2">
            {MATCH_TRANSITIONS[m.status].map((next) => (
              <Button
                key={next}
                variant="secondary"
                onClick={() => {
                  if (next === "finished" && m.home_score == null) {
                    setError(
                      "Enter the final score below before finishing the match.",
                    );
                    return;
                  }
                  if (next === "live")
                    return patch({
                      status: "live",
                      home_score: 0,
                      away_score: 0,
                    });
                  return patch({ status: next });
                }}
              >
                Mark {next}
              </Button>
            ))}
            {!started && m.status !== "cancelled" && (
              <Button
                variant="danger"
                onClick={async () => {
                  if (!window.confirm("Delete this match?")) return;
                  try {
                    await apiFetch(`/matches/${id}`, { method: "DELETE" });
                    await qc.invalidateQueries({ queryKey: ["matches"] });
                    router.replace("/matches");
                  } catch (e) {
                    setError(
                      e instanceof ApiError ? e.message : "Request failed",
                    );
                  }
                }}
              >
                Delete
              </Button>
            )}
          </div>
          {started && (
            <ScoreEditor
              match={m}
              onSave={(home, away) =>
                patch({ home_score: home, away_score: away })
              }
            />
          )}
        </Card>
      )}

      {started && (
        <>
          <EventsSection
            match={m}
            editable={m.editable}
            onChange={refresh}
            onError={setError}
          />
          <StatsSection
            match={m}
            editable={m.editable}
            onChange={refresh}
            onError={setError}
          />
        </>
      )}
    </div>
  );
}

function ScoreEditor({
  match,
  onSave,
}: {
  match: MatchDetail;
  onSave: (home: number, away: number) => void;
}) {
  const [home, setHome] = useState(String(match.home_score ?? 0));
  const [away, setAway] = useState(String(match.away_score ?? 0));
  const valid = /^\d{1,2}$/.test(home) && /^\d{1,2}$/.test(away);
  return (
    <div className="flex items-end gap-2 text-sm">
      <label>
        {match.home_club_name}
        <input
          aria-label="Home score"
          inputMode="numeric"
          value={home}
          onChange={(e) => setHome(e.target.value)}
          className={`${input} ml-2 w-14`}
        />
      </label>
      <label>
        {match.away_club_name}
        <input
          aria-label="Away score"
          inputMode="numeric"
          value={away}
          onChange={(e) => setAway(e.target.value)}
          className={`${input} ml-2 w-14`}
        />
      </label>
      <Button
        variant="secondary"
        disabled={!valid}
        onClick={() => onSave(Number(home), Number(away))}
      >
        Save score
      </Button>
    </div>
  );
}

function EventsSection({
  match,
  editable,
  onChange,
  onError,
}: {
  match: MatchDetail;
  editable: boolean;
  onChange: () => void;
  onError: (m: string | null) => void;
}) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EventValues>({
    resolver: zodResolver(eventSchema),
    defaultValues: { event_type: "goal" },
  });
  const submit = handleSubmit(async (v) => {
    onError(null);
    try {
      await apiFetch(`/matches/${match.id}/events`, {
        method: "POST",
        json: {
          event_type: v.event_type,
          minute: Number(v.minute),
          club_id: v.club_id,
          description: v.description || null,
        },
      });
      reset({
        event_type: v.event_type,
        club_id: v.club_id,
        minute: "",
        description: "",
      });
      onChange();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Request failed");
    }
  });
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Match events</h2>
      {match.events.length === 0 ? (
        <Empty>No events recorded.</Empty>
      ) : (
        <ol className="space-y-1 text-sm">
          {match.events.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-1.5 dark:border-slate-800"
            >
              <span>
                <strong>{e.minute}&apos;</strong>{" "}
                {e.event_type.replace("_", " ")} — {e.club_name}
                {e.player_name ? ` (${e.player_name})` : ""}
                {e.description ? ` · ${e.description}` : ""}
              </span>
              {editable && (
                <Button
                  variant="secondary"
                  onClick={async () => {
                    try {
                      await apiFetch(`/matches/${match.id}/events/${e.id}`, {
                        method: "DELETE",
                      });
                      onChange();
                    } catch (err) {
                      onError(
                        err instanceof ApiError
                          ? err.message
                          : "Request failed",
                      );
                    }
                  }}
                >
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ol>
      )}
      {editable && (
        <form
          onSubmit={submit}
          className="grid max-w-2xl grid-cols-[9rem_5rem_1fr_1fr_auto] items-start gap-2"
          noValidate
        >
          <select
            aria-label="Event type"
            className={input}
            {...register("event_type")}
          >
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
          <div>
            <input
              aria-label="Minute"
              placeholder="Min"
              className={`${input} w-full`}
              {...register("minute")}
            />
            <ErrorText>{errors.minute?.message}</ErrorText>
          </div>
          <div>
            <select
              aria-label="Club"
              className={`${input} w-full`}
              {...register("club_id")}
            >
              <option value="">Club…</option>
              <option value={match.home_club_id}>{match.home_club_name}</option>
              <option value={match.away_club_id}>{match.away_club_name}</option>
            </select>
            <ErrorText>{errors.club_id?.message}</ErrorText>
          </div>
          <input
            aria-label="Note"
            placeholder="Note (optional)"
            className={input}
            {...register("description")}
          />
          <Button type="submit" disabled={isSubmitting}>
            Add
          </Button>
        </form>
      )}
    </section>
  );
}

function StatsSection({
  match,
  editable,
  onChange,
  onError,
}: {
  match: MatchDetail;
  editable: boolean;
  onChange: () => void;
  onError: (m: string | null) => void;
}) {
  const toForm = (s: StatsSide | null) =>
    Object.fromEntries(
      STAT_FIELDS.map(([k]) => [k, s?.[k] != null ? String(s[k]) : ""]),
    );
  const [home, setHome] = useState<Record<string, string>>(() =>
    toForm(match.statistics.home),
  );
  const [away, setAway] = useState<Record<string, string>>(() =>
    toForm(match.statistics.away),
  );
  const [problems, setProblems] = useState<string[]>([]);

  async function save() {
    const checks = [
      statsSideSchema.safeParse(home),
      statsSideSchema.safeParse(away),
    ];
    const issues = checks.flatMap((c, i) =>
      c.success
        ? []
        : c.error.issues.map(
            (x) => `${i ? "Away" : "Home"} ${String(x.path[0])}: ${x.message}`,
          ),
    );
    setProblems(issues);
    if (issues.length) return;
    const clean = (f: Record<string, string>) => {
      const entries = Object.entries(f).filter(([, v]) => v.trim() !== "");
      return entries.length
        ? Object.fromEntries(entries.map(([k, v]) => [k, Number(v)]))
        : null;
    };
    onError(null);
    try {
      await apiFetch(`/matches/${match.id}/statistics`, {
        method: "PUT",
        json: { home: clean(home), away: clean(away) },
      });
      onChange();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Request failed");
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Team statistics</h2>
      <table className="w-full max-w-xl text-sm">
        <thead className="text-xs uppercase opacity-60">
          <tr>
            <th className="text-left">&nbsp;</th>
            <th>{match.home_club_name}</th>
            <th>{match.away_club_name}</th>
          </tr>
        </thead>
        <tbody>
          {STAT_FIELDS.map(([key, label]) => (
            <tr
              key={key}
              className="border-b border-slate-100 dark:border-slate-900"
            >
              <td className="py-1">{label}</td>
              {(
                [
                  [home, setHome, "Home"],
                  [away, setAway, "Away"],
                ] as const
              ).map(([values, setValues, side]) => (
                <td key={side} className="text-center">
                  {editable ? (
                    <input
                      aria-label={`${side} ${label}`}
                      inputMode="numeric"
                      value={values[key]}
                      onChange={(e) =>
                        setValues({ ...values, [key]: e.target.value })
                      }
                      className={`${input} w-16 text-center`}
                    />
                  ) : (
                    values[key] || "—"
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {problems.map((p) => (
        <ErrorText key={p}>{p}</ErrorText>
      ))}
      {editable && <Button onClick={save}>Save statistics</Button>}
    </section>
  );
}
