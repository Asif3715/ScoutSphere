"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { reportSchema, type ReportValues } from "@/lib/schemas";
import {
  POSITIONS,
  RATING_GROUPS,
  RECOMMENDATIONS,
  label,
  type MatchSummary,
  type Page,
  type PlayerSummary,
  type ReportDetail,
} from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";
const TEXT_FIELDS = [
  ["strengths", "Strengths"],
  ["weaknesses", "Weaknesses"],
  ["development_areas", "Development areas"],
  ["general_observations", "General observations"],
] as const;

export function toReportValues(
  r?: ReportDetail,
  defaults?: Partial<ReportValues>,
): ReportValues {
  const ratings: Record<string, string> = {};
  for (const attrs of Object.values(RATING_GROUPS))
    for (const a of attrs)
      ratings[a] = r?.ratings[a] ? String(r.ratings[a]) : "";
  return {
    player_id: r?.player_id ?? defaults?.player_id ?? "",
    match_id: r?.match_id ?? defaults?.match_id ?? "",
    observed_on: r?.observed_on ?? new Date().toISOString().slice(0, 10),
    position_observed: r?.position_observed ?? "",
    recommendation: r?.recommendation ?? "",
    strengths: r?.strengths ?? "",
    weaknesses: r?.weaknesses ?? "",
    development_areas: r?.development_areas ?? "",
    general_observations: r?.general_observations ?? "",
    ratings,
  };
}

export function ReportEditor({
  report,
  defaults,
  playerName,
  submitLabel,
  onSubmit,
}: {
  report?: ReportDetail;
  defaults?: Partial<ReportValues>;
  playerName?: string;
  submitLabel: string;
  onSubmit: (values: ReportValues) => Promise<void>;
}) {
  const { activeOrgId } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const [playerSearch, setPlayerSearch] = useState("");
  const editing = !!report;
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ReportValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: toReportValues(report, defaults),
  });

  const fixedPlayer = editing || !!defaults?.player_id;
  const players = useQuery({
    queryKey: ["players", activeOrgId, "report-search", playerSearch],
    queryFn: () =>
      apiFetch<Page<PlayerSummary>>(
        `/players?q=${encodeURIComponent(playerSearch)}&page_size=10`,
      ),
    enabled: !!activeOrgId && !fixedPlayer && playerSearch.trim().length >= 2,
  });
  const matches = useQuery({
    queryKey: ["matches", activeOrgId, "report-options"],
    queryFn: () =>
      apiFetch<Page<MatchSummary>>("/matches?page_size=100&status=finished"),
    enabled: !!activeOrgId && !editing && !defaults?.match_id,
  });

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await onSubmit(values);
    } catch (e) {
      setFormError(
        e instanceof ApiError ? e.message : "Could not reach the server",
      );
    }
  });

  return (
    <form
      method="post"
      onSubmit={submit}
      className="max-w-3xl space-y-6"
      noValidate
    >
      <Card className="grid grid-cols-2 gap-4">
        <div className="col-span-2 space-y-1">
          <label htmlFor="player_id" className="block text-sm font-medium">
            Player
          </label>
          {fixedPlayer ? (
            <>
              <p className="text-sm font-semibold">
                {playerName ?? report?.player_name}
              </p>
              <input type="hidden" {...register("player_id")} />
            </>
          ) : (
            <>
              <input
                type="search"
                aria-label="Search players"
                placeholder="Search players (2+ letters)…"
                value={playerSearch}
                onChange={(e) => setPlayerSearch(e.target.value)}
                className={select}
              />
              <select
                id="player_id"
                className={select}
                {...register("player_id")}
              >
                <option value="">Choose…</option>
                {players.data?.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.age})
                  </option>
                ))}
              </select>
            </>
          )}
          <ErrorText>{errors.player_id?.message}</ErrorText>
        </div>
        {!editing && !defaults?.match_id && (
          <div className="space-y-1">
            <label htmlFor="match_id" className="block text-sm font-medium">
              Match (optional)
            </label>
            <select id="match_id" className={select} {...register("match_id")}>
              <option value="">None</option>
              {matches.data?.items.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.home_club_name} v {m.away_club_name}
                </option>
              ))}
            </select>
          </div>
        )}
        <Field
          label="Date observed"
          type="date"
          error={errors.observed_on?.message}
          {...register("observed_on")}
        />
        <div className="space-y-1">
          <label
            htmlFor="position_observed"
            className="block text-sm font-medium"
          >
            Position observed
          </label>
          <select
            id="position_observed"
            className={select}
            {...register("position_observed")}
          >
            <option value="">—</option>
            {POSITIONS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>
      </Card>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Ratings (1–10)</h2>
        <p className="text-xs opacity-60">
          These are your subjective ratings. They are kept separate from
          objective match statistics. Leave blank what you did not observe.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {Object.entries(RATING_GROUPS).map(([group, attrs]) => (
            <Card key={group} className="space-y-2">
              <h3 className="text-sm font-semibold capitalize">{group}</h3>
              {attrs.map((attr) => (
                <div
                  key={attr}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <label htmlFor={`rating-${attr}`} className="capitalize">
                    {label(attr)}
                  </label>
                  <input
                    id={`rating-${attr}`}
                    inputMode="numeric"
                    maxLength={2}
                    aria-invalid={!!errors.ratings?.[attr]}
                    className="w-14 rounded-[2px] border border-line-strong bg-transparent px-2 py-1 text-center text-sm aria-[invalid=true]:border-bad"
                    {...register(`ratings.${attr}`)}
                  />
                </div>
              ))}
            </Card>
          ))}
        </div>
        {errors.ratings && (
          <ErrorText>Ratings must be whole numbers from 1 to 10.</ErrorText>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Written observations</h2>
        {TEXT_FIELDS.map(([name, text]) => (
          <div key={name} className="space-y-1">
            <label htmlFor={name} className="block text-sm font-medium">
              {text}
            </label>
            <textarea
              id={name}
              rows={3}
              className={select}
              {...register(name)}
            />
          </div>
        ))}
        <div className="space-y-1">
          <label htmlFor="recommendation" className="block text-sm font-medium">
            Final recommendation
          </label>
          <select
            id="recommendation"
            className={select}
            {...register("recommendation")}
          >
            <option value="">Not decided</option>
            {RECOMMENDATIONS.map((r) => (
              <option key={r} value={r}>
                {label(r)}
              </option>
            ))}
          </select>
        </div>
      </section>

      <ErrorText>{formError}</ErrorText>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
