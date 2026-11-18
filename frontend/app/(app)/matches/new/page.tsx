"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { matchSchema, toIsoUtc, type MatchValues } from "@/lib/schemas";
import type {
  Competition,
  CompetitionDetail,
  MatchDetail,
  Page,
  SeasonDetail,
} from "@/lib/types";

const select =
  "w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm";

export default function NewMatchPage() {
  const { activeOrgId, can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [competitionId, setCompetitionId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<MatchValues>({ resolver: zodResolver(matchSchema) });
  const seasonId = useWatch({ control, name: "season_id" });

  const comps = useQuery({
    queryKey: ["competitions", activeOrgId, "options"],
    queryFn: () => apiFetch<Page<Competition>>("/competitions?page_size=100"),
    enabled: !!activeOrgId,
  });
  const detail = useQuery({
    queryKey: ["competition", activeOrgId, competitionId],
    queryFn: () =>
      apiFetch<CompetitionDetail>(`/competitions/${competitionId}`),
    enabled: !!activeOrgId && !!competitionId,
  });
  const season = useQuery({
    queryKey: ["season", activeOrgId, seasonId],
    queryFn: () => apiFetch<SeasonDetail>(`/seasons/${seasonId}`),
    enabled: !!activeOrgId && !!seasonId,
  });

  if (!can("matches:manage"))
    return (
      <p className="text-sm">You do not have permission to add matches.</p>
    );

  const submit = handleSubmit(async (v) => {
    setFormError(null);
    try {
      const m = await apiFetch<MatchDetail>("/matches", {
        method: "POST",
        json: {
          season_id: v.season_id,
          home_club_id: v.home_club_id,
          away_club_id: v.away_club_id,
          kickoff_at: toIsoUtc(v.kickoff_at),
          venue: v.venue || null,
          round_label: v.round_label || null,
        },
      });
      await qc.invalidateQueries({ queryKey: ["matches"] });
      router.push(`/matches/${m.id}`);
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Request failed");
    }
  });

  const clubs = season.data?.participants ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Add match</h1>
      <form
        method="post"
        onSubmit={submit}
        className="max-w-xl space-y-4"
        noValidate
      >
        <div className="space-y-1">
          <label htmlFor="competition" className="block text-sm font-medium">
            Competition
          </label>
          <select
            id="competition"
            className={select}
            value={competitionId}
            onChange={(e) => setCompetitionId(e.target.value)}
          >
            <option value="">Choose…</option>
            {comps.data?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.is_global ? " (global)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="season_id" className="block text-sm font-medium">
            Season
          </label>
          <select id="season_id" className={select} {...register("season_id")}>
            <option value="">Choose…</option>
            {detail.data?.seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <ErrorText>{errors.season_id?.message}</ErrorText>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {(["home_club_id", "away_club_id"] as const).map((field) => (
            <div key={field} className="space-y-1">
              <label htmlFor={field} className="block text-sm font-medium">
                {field === "home_club_id" ? "Home club" : "Away club"}
              </label>
              <select id={field} className={select} {...register(field)}>
                <option value="">Choose…</option>
                {clubs.map((c) => (
                  <option key={c.club_id} value={c.club_id}>
                    {c.club_name}
                  </option>
                ))}
              </select>
              <ErrorText>{errors[field]?.message}</ErrorText>
            </div>
          ))}
        </div>
        {seasonId && clubs.length < 2 && (
          <p className="text-xs text-amber-700">
            This season needs at least two participating clubs first.
          </p>
        )}
        <Field
          label="Kick-off"
          type="datetime-local"
          error={errors.kickoff_at?.message}
          {...register("kickoff_at")}
        />
        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Venue"
            error={errors.venue?.message}
            {...register("venue")}
          />
          <Field
            label="Round"
            error={errors.round_label?.message}
            {...register("round_label")}
          />
        </div>
        <ErrorText>{formError}</ErrorText>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : "Create match"}
        </Button>
      </form>
    </div>
  );
}
