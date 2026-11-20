"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import {
  PageHeader,
  RowLink,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { teamSchema, type TeamValues } from "@/lib/schemas";
import {
  label,
  TEAM_TYPES,
  type Club,
  type Page,
  type Team,
} from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

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
      <PageHeader
        eyebrow="Club"
        title="Teams"
        meta={
          teams.data
            ? `${teams.data.length} team${teams.data.length === 1 ? "" : "s"} across your clubs`
            : "Squads within your clubs: first team, reserves, academy."
        }
      />
      <div
        className={`grid items-start gap-6 ${manage ? "lg:grid-cols-[minmax(0,1fr)_20rem]" : ""}`}
      >
        <TableCard>
          <table className="data-table">
            <thead>
              <tr>
                <th>Team</th>
                <th className="hidden sm:table-cell">Club</th>
                <th>Type</th>
                <th className="num">Players</th>
              </tr>
            </thead>
            {teams.isLoading && <SkeletonRows cols={4} rows={4} />}
            {teams.error && (
              <TableMessage cols={4}>
                <span className="text-bad">{teams.error.message}</span>
              </TableMessage>
            )}
            {teams.data && teams.data.length === 0 && (
              <TableMessage cols={4}>
                No teams yet. Register a club, then create its teams.
              </TableMessage>
            )}
            {teams.data && teams.data.length > 0 && (
              <tbody>
                {teams.data.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <RowLink href={`/teams/${t.id}`}>{t.name}</RowLink>
                      <span className="sub sm:hidden">{t.club_name}</span>
                    </td>
                    <td className="hidden sm:table-cell">{t.club_name}</td>
                    <td>
                      <span className="chip chip-outline">
                        {label(t.team_type)}
                      </span>
                    </td>
                    <td className="num">{t.active_players}</td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        </TableCard>

        {manage && (
          <Card className="space-y-3">
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
                <select
                  id="club_id"
                  className={select}
                  {...register("club_id")}
                >
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
                <label
                  htmlFor="team_type"
                  className="block text-sm font-medium"
                >
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
    </div>
  );
}
