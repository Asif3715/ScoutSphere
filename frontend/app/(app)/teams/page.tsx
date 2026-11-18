"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { teamSchema, type TeamValues } from "@/lib/schemas";
import { TEAM_TYPES, type Club, type Page, type Team } from "@/lib/types";

const select =
  "w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm";

export default function TeamsPage() {
  const { activeOrgId, can } = useAuth();
  const qc = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const manage = can("clubs:manage");

  const teams = useQuery({
    queryKey: ["teams", activeOrgId],
    queryFn: () => apiFetch<Team[]>("/teams"),
    enabled: !!activeOrgId,
  });
  const clubs = useQuery({
    queryKey: ["clubs", activeOrgId, "options"],
    queryFn: () => apiFetch<Page<Club>>("/clubs?scope=mine&page_size=100"),
    enabled: !!activeOrgId && manage,
  });
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<TeamValues>({
    resolver: zodResolver(teamSchema),
    defaultValues: { team_type: "senior" },
  });

  const create = handleSubmit(async (v) => {
    setFormError(null);
    try {
      await apiFetch("/teams", { method: "POST", json: v });
      reset({ team_type: v.team_type, club_id: v.club_id, name: "" });
      qc.invalidateQueries({ queryKey: ["teams"] });
    } catch (e) {
      if (e instanceof ApiError && e.code === "team_exists")
        setError("name", { message: e.message });
      else setFormError(e instanceof ApiError ? e.message : "Request failed");
    }
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Teams</h1>
      <ErrorText>{teams.error?.message}</ErrorText>
      {teams.isLoading && <p aria-busy="true">Loading…</p>}
      {teams.data && teams.data.length === 0 && (
        <Empty>No teams yet. Register a club, then create its teams.</Empty>
      )}
      {teams.data && teams.data.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase opacity-60 dark:border-slate-800">
            <tr>
              <th className="py-2">Team</th>
              <th>Club</th>
              <th>Type</th>
              <th>Players</th>
            </tr>
          </thead>
          <tbody>
            {teams.data.map((t) => (
              <tr
                key={t.id}
                className="border-b border-slate-100 dark:border-slate-900"
              >
                <td className="py-2">
                  <Link
                    href={`/teams/${t.id}`}
                    className="font-medium text-teal-600 hover:underline"
                  >
                    {t.name}
                  </Link>
                </td>
                <td>{t.club_name}</td>
                <td>{t.team_type}</td>
                <td>{t.active_players}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {manage && (
        <Card className="max-w-xl space-y-3">
          <h2 className="font-semibold">Create team</h2>
          <form
            method="post"
            onSubmit={create}
            className="space-y-3"
            noValidate
          >
            <div className="space-y-1">
              <label htmlFor="club_id" className="block text-sm font-medium">
                Club
              </label>
              <select id="club_id" className={select} {...register("club_id")}>
                <option value="">Choose…</option>
                {clubs.data?.items.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <ErrorText>{errors.club_id?.message}</ErrorText>
            </div>
            <Field
              label="Team name"
              error={errors.name?.message}
              {...register("name")}
            />
            <div className="space-y-1">
              <label htmlFor="team_type" className="block text-sm font-medium">
                Type
              </label>
              <select
                id="team_type"
                className={select}
                {...register("team_type")}
              >
                {TEAM_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <ErrorText>{formError}</ErrorText>
            <Button type="submit" disabled={isSubmitting}>
              Create team
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
