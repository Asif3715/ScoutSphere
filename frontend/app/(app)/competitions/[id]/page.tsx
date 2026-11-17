"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { seasonSchema, type SeasonValues } from "@/lib/schemas";
import type { CompetitionDetail } from "@/lib/types";

export default function CompetitionPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId } = useAuth();
  const qc = useQueryClient();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    data: comp,
    error,
    isLoading,
  } = useQuery({
    queryKey: ["competition", activeOrgId, id],
    queryFn: () => apiFetch<CompetitionDetail>(`/competitions/${id}`),
    enabled: !!activeOrgId,
  });
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SeasonValues>({ resolver: zodResolver(seasonSchema) });

  if (isLoading) return <p aria-busy="true">Loading…</p>;
  if (error || !comp) {
    return (
      <div className="space-y-2">
        <ErrorText>{error?.message ?? "Competition not found"}</ErrorText>
        <Link href="/competitions" className="text-sm text-teal-600 underline">
          Back to competitions
        </Link>
      </div>
    );
  }

  const addSeason = handleSubmit(async (v) => {
    setFormError(null);
    try {
      await apiFetch(`/competitions/${id}/seasons`, {
        method: "POST",
        json: v,
      });
      reset();
      qc.invalidateQueries({ queryKey: ["competition", activeOrgId, id] });
    } catch (e) {
      if (e instanceof ApiError && e.code === "season_exists")
        setError("name", { message: e.message });
      else setFormError(e instanceof ApiError ? e.message : "Request failed");
    }
  });

  async function archive() {
    if (!window.confirm(`Archive ${comp!.name}?`)) return;
    try {
      await apiFetch(`/competitions/${id}`, { method: "DELETE" });
      await qc.invalidateQueries({ queryKey: ["competitions"] });
      router.replace("/competitions");
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Request failed");
    }
  }

  return (
    <div className="space-y-6">
      <Link href="/competitions" className="text-sm text-teal-600 underline">
        ← Competitions
      </Link>
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{comp.name}</h1>
          <p className="text-sm opacity-70">
            {comp.competition_type.replace("_", " ")}
            {comp.country ? ` · ${comp.country}` : ""}
            {comp.is_global ? " · Global competition (read-only)" : ""}
          </p>
        </div>
        {comp.editable && (
          <Button variant="danger" onClick={archive}>
            Archive
          </Button>
        )}
      </header>
      <ErrorText>{formError}</ErrorText>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Seasons</h2>
        {comp.seasons.length === 0 ? (
          <Empty>No seasons yet.</Empty>
        ) : (
          <ul className="space-y-2">
            {comp.seasons.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
              >
                <div>
                  <Link
                    href={`/seasons/${s.id}`}
                    className="font-medium text-teal-600 hover:underline"
                  >
                    {s.name}
                  </Link>
                  <p className="text-xs opacity-60">
                    {s.start_date} → {s.end_date} · {s.participant_count} clubs
                    · {s.match_count} matches
                  </p>
                </div>
                <Link
                  href={`/matches?season_id=${s.id}`}
                  className="text-xs text-teal-600 underline"
                >
                  View matches
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {comp.editable && (
        <Card className="max-w-xl space-y-3">
          <h2 className="font-semibold">Add season</h2>
          <form
            onSubmit={addSeason}
            className="grid grid-cols-2 gap-3"
            noValidate
          >
            <div className="col-span-2">
              <Field
                label="Name (e.g. 2025/26)"
                error={errors.name?.message}
                {...register("name")}
              />
            </div>
            <Field
              label="Starts"
              type="date"
              error={errors.start_date?.message}
              {...register("start_date")}
            />
            <Field
              label="Ends"
              type="date"
              error={errors.end_date?.message}
              {...register("end_date")}
            />
            <div className="col-span-2">
              <Button type="submit" disabled={isSubmitting}>
                Add season
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}
