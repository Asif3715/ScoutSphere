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
import {
  assignmentPayload,
  assignmentSchema,
  type AssignmentValues,
} from "@/lib/schemas";
import type {
  AssignmentDetail,
  Competition,
  MatchSummary,
  Page,
  PlayerSummary,
  Scout,
} from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

export default function NewAssignmentPage() {
  const { activeOrgId, can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const [playerSearch, setPlayerSearch] = useState("");
  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<AssignmentValues>({
    resolver: zodResolver(assignmentSchema),
    defaultValues: { target_type: "match", assign_now: true },
  });
  const targetType = useWatch({ control, name: "target_type" });

  const scouts = useQuery({
    queryKey: ["scouts", activeOrgId, "options"],
    queryFn: () => apiFetch<Page<Scout>>("/scouts?page_size=100"),
    enabled: !!activeOrgId,
  });
  const matches = useQuery({
    queryKey: ["matches", activeOrgId, "options"],
    queryFn: () =>
      apiFetch<Page<MatchSummary>>("/matches?page_size=100&sort=kickoff_asc"),
    enabled: !!activeOrgId && targetType === "match",
  });
  const comps = useQuery({
    queryKey: ["competitions", activeOrgId, "options"],
    queryFn: () => apiFetch<Page<Competition>>("/competitions?page_size=100"),
    enabled: !!activeOrgId && targetType === "competition",
  });
  const players = useQuery({
    queryKey: ["players", activeOrgId, "assign-search", playerSearch],
    queryFn: () =>
      apiFetch<Page<PlayerSummary>>(
        `/players?q=${encodeURIComponent(playerSearch)}&page_size=10`,
      ),
    enabled:
      !!activeOrgId &&
      targetType === "player" &&
      playerSearch.trim().length >= 2,
  });

  if (!can("assignments:manage"))
    return (
      <p className="text-sm">
        You do not have permission to create assignments.
      </p>
    );

  const submit = handleSubmit(async (v) => {
    setFormError(null);
    try {
      const a = await apiFetch<AssignmentDetail>("/assignments", {
        method: "POST",
        json: assignmentPayload(v),
      });
      await qc.invalidateQueries({ queryKey: ["assignments"] });
      await qc.invalidateQueries({ queryKey: ["assignment-stats"] });
      router.push(`/assignments/${a.id}`);
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Request failed");
    }
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">New assignment</h1>
      <form
        method="post"
        onSubmit={submit}
        className="max-w-xl space-y-4"
        noValidate
      >
        <div className="space-y-1">
          <label htmlFor="scout_id" className="block text-sm font-medium">
            Scout
          </label>
          <select id="scout_id" className={select} {...register("scout_id")}>
            <option value="">Choose…</option>
            {scouts.data?.items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.full_name}
              </option>
            ))}
          </select>
          <ErrorText>{errors.scout_id?.message}</ErrorText>
          {scouts.data && scouts.data.items.length === 0 && (
            <p className="text-xs text-warn">
              No active scout profiles yet. Members can create one under Scouts.
            </p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="target_type" className="block text-sm font-medium">
            What should they scout?
          </label>
          <select
            id="target_type"
            className={select}
            {...register("target_type", {
              onChange: () => setValue("target_id", ""),
            })}
          >
            <option value="match">A match</option>
            <option value="competition">A competition</option>
            <option value="player">A specific player</option>
          </select>
        </div>

        <div className="space-y-1">
          <label htmlFor="target_id" className="block text-sm font-medium">
            Target
          </label>
          {targetType === "player" && (
            <input
              type="search"
              aria-label="Search players"
              placeholder="Search players (2+ letters)…"
              value={playerSearch}
              onChange={(e) => setPlayerSearch(e.target.value)}
              className={select}
            />
          )}
          <select id="target_id" className={select} {...register("target_id")}>
            <option value="">Choose…</option>
            {targetType === "match" &&
              matches.data?.items.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.home_club_name} v {m.away_club_name} ·{" "}
                  {new Date(m.kickoff_at).toLocaleDateString()}
                </option>
              ))}
            {targetType === "competition" &&
              comps.data?.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            {targetType === "player" &&
              players.data?.items.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name} ({p.age})
                </option>
              ))}
          </select>
          <ErrorText>{errors.target_id?.message}</ErrorText>
        </div>

        <Field
          label="Title"
          error={errors.title?.message}
          {...register("title")}
        />
        <div className="space-y-1">
          <label htmlFor="instructions" className="block text-sm font-medium">
            Instructions
          </label>
          <textarea
            id="instructions"
            rows={3}
            className={select}
            {...register("instructions")}
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="criteria" className="block text-sm font-medium">
            Evaluation criteria
          </label>
          <textarea
            id="criteria"
            rows={2}
            className={select}
            {...register("criteria")}
          />
        </div>
        <Field
          label="Deadline"
          type="datetime-local"
          error={errors.deadline?.message}
          {...register("deadline")}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("assign_now")} /> Send to the
          scout now (otherwise save as a draft)
        </label>
        <ErrorText>{formError}</ErrorText>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : "Create assignment"}
        </Button>
      </form>
    </div>
  );
}
