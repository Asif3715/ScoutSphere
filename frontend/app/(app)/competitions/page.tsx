"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { competitionSchema, type CompetitionValues } from "@/lib/schemas";
import { COMPETITION_TYPES, type Competition, type Page } from "@/lib/types";

const select =
  "w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm";

export default function CompetitionsPage() {
  const { activeOrgId, can } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [formError, setFormError] = useState<string | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["competitions", activeOrgId, q, page],
    queryFn: () =>
      apiFetch<Page<Competition>>(
        `/competitions?page=${page}&page_size=15${q ? `&q=${encodeURIComponent(q)}` : ""}`,
      ),
    enabled: !!activeOrgId,
  });
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<CompetitionValues>({
    resolver: zodResolver(competitionSchema),
    defaultValues: { competition_type: "league" },
  });

  const create = handleSubmit(async (v) => {
    setFormError(null);
    try {
      await apiFetch("/competitions", {
        method: "POST",
        json: { ...v, country: v.country || null },
      });
      reset({ competition_type: v.competition_type, name: "", country: "" });
      qc.invalidateQueries({ queryKey: ["competitions"] });
    } catch (e) {
      if (e instanceof ApiError && e.code === "competition_exists")
        setError("name", { message: e.message });
      else setFormError(e instanceof ApiError ? e.message : "Request failed");
    }
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Competitions</h1>
      <input
        type="search"
        aria-label="Search competitions"
        placeholder="Search by name…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
        className="rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm"
      />
      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && <Empty>No competitions yet.</Empty>}
      {data && data.items.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase opacity-60 dark:border-slate-800">
              <tr>
                <th className="py-2">Name</th>
                <th>Type</th>
                <th>Country</th>
                <th>Seasons</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr
                  key={c.id}
                  className="border-b border-slate-100 dark:border-slate-900"
                >
                  <td className="py-2">
                    <Link
                      href={`/competitions/${c.id}`}
                      className="font-medium text-teal-600 hover:underline"
                    >
                      {c.name}
                    </Link>
                    {c.is_global && (
                      <span className="ml-2 text-xs opacity-50">global</span>
                    )}
                  </td>
                  <td>{c.competition_type.replace("_", " ")}</td>
                  <td>{c.country ?? "—"}</td>
                  <td>{c.season_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onChange={setPage}
          />
        </>
      )}

      {can("matches:manage") && (
        <Card className="max-w-xl space-y-3">
          <h2 className="font-semibold">Create competition</h2>
          <form onSubmit={create} className="space-y-3" noValidate>
            <Field
              label="Name"
              error={errors.name?.message}
              {...register("name")}
            />
            <Field
              label="Country"
              error={errors.country?.message}
              {...register("country")}
            />
            <div className="space-y-1">
              <label
                htmlFor="competition_type"
                className="block text-sm font-medium"
              >
                Type
              </label>
              <select
                id="competition_type"
                className={select}
                {...register("competition_type")}
              >
                {COMPETITION_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <ErrorText>{formError}</ErrorText>
            <Button type="submit" disabled={isSubmitting}>
              Create competition
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
