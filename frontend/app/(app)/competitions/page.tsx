"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import {
  PageHeader,
  RowLink,
  SearchInput,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { Button, Card, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { competitionSchema, type CompetitionValues } from "@/lib/schemas";
import {
  COMPETITION_TYPES,
  label,
  type Competition,
  type Page,
} from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

export default function CompetitionsPage() {
  const { activeOrgId, can } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [formError, setFormError] = useState<string | null>(null);
  const manage = can("matches:manage");

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
      <PageHeader
        eyebrow="Fixtures"
        title="Competitions"
        meta="Leagues and cups, each with its seasons and matches."
      />
      <div
        className={`grid items-start gap-6 ${manage ? "lg:grid-cols-[minmax(0,1fr)_20rem]" : ""}`}
      >
        <TableCard
          toolbar={
            <SearchInput
              label="Search competitions"
              placeholder="Search by name…"
              value={q}
              onChange={(e) => (setQ(e.target.value), setPage(1))}
              className="w-full sm:w-64"
            />
          }
          footer={
            data &&
            data.total > 0 && (
              <Pagination
                page={data.page}
                pageSize={data.page_size}
                total={data.total}
                onChange={setPage}
              />
            )
          }
        >
          <table className="data-table">
            <thead>
              <tr>
                <th>Competition</th>
                <th>Type</th>
                <th className="hidden sm:table-cell">Country</th>
                <th className="num">Seasons</th>
              </tr>
            </thead>
            {isLoading && <SkeletonRows cols={4} rows={4} />}
            {error && (
              <TableMessage cols={4}>
                <span className="text-bad">{error.message}</span>
              </TableMessage>
            )}
            {data && data.items.length === 0 && (
              <TableMessage cols={4}>
                {q
                  ? "No competitions match that search."
                  : "No competitions yet."}
              </TableMessage>
            )}
            {data && data.items.length > 0 && (
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <RowLink href={`/competitions/${c.id}`}>{c.name}</RowLink>
                      {c.is_global && (
                        <span className="sub">Global, shared by all clubs</span>
                      )}
                    </td>
                    <td>
                      <span className="chip chip-outline">
                        {label(c.competition_type)}
                      </span>
                    </td>
                    <td className="hidden sm:table-cell">
                      {c.country ?? <span className="opacity-40">—</span>}
                    </td>
                    <td className="num">{c.season_count}</td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        </TableCard>

        {manage && (
          <Card className="space-y-3">
            <h2 className="font-semibold">Create competition</h2>
            <form
              method="post"
              onSubmit={create}
              className="space-y-3"
              noValidate
            >
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
    </div>
  );
}
