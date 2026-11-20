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
import { shortlistSchema, type ShortlistValues } from "@/lib/schemas";
import { PRIORITIES, type Page, type ShortlistSummary } from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

export default function ShortlistsPage() {
  const { activeOrgId, can } = useAuth();
  const qc = useQueryClient();
  const [scope, setScope] = useState<"all" | "mine" | "shared">("all");
  const [page, setPage] = useState(1);
  const [formError, setFormError] = useState<string | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["shortlists", activeOrgId, scope, page],
    queryFn: () =>
      apiFetch<Page<ShortlistSummary>>(
        `/recruitment/shortlists?scope=${scope}&page=${page}&page_size=15`,
      ),
    enabled: !!activeOrgId,
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ShortlistValues>({
    resolver: zodResolver(shortlistSchema),
    defaultValues: { priority: "medium" },
  });

  const create = handleSubmit(async (v) => {
    setFormError(null);
    try {
      await apiFetch("/recruitment/shortlists", {
        method: "POST",
        json: {
          name: v.name,
          description: v.description || null,
          priority: v.priority,
          requirement_id: v.requirement_id || null,
        },
      });
      reset({ priority: v.priority, name: "", description: "" });
      qc.invalidateQueries({ queryKey: ["shortlists"] });
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Request failed");
    }
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Shortlists</h1>
      <p className="text-xs opacity-60">
        A shortlist is private to you until you share it with colleagues.
      </p>
      <div role="tablist" className="flex gap-2">
        {(["all", "mine", "shared"] as const).map((s) => (
          <Button
            key={s}
            role="tab"
            aria-selected={scope === s}
            variant={scope === s ? "primary" : "secondary"}
            onClick={() => (setScope(s), setPage(1))}
          >
            {s === "all"
              ? "All"
              : s === "mine"
                ? "Created by me"
                : "Shared with me"}
          </Button>
        ))}
      </div>
      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && data.items.length === 0 && (
        <Empty>No shortlists here yet.</Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <ul className="grid gap-3 sm:grid-cols-2">
            {data.items.map((s) => (
              <li key={s.id} className="rounded-[3px] border border-line p-4">
                <Link
                  href={`/shortlists/${s.id}`}
                  className="font-semibold text-link hover:underline"
                >
                  {s.name}
                </Link>
                <p className="text-xs opacity-60">
                  {s.player_count} player{s.player_count === 1 ? "" : "s"} ·
                  priority {s.priority}
                  {!s.is_owner && ` · shared by ${s.owner_name}`}
                </p>
                {s.requirement_title && (
                  <p className="text-xs opacity-70">
                    For: {s.requirement_title}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onChange={setPage}
          />
        </>
      )}

      {can("recruitment:manage") && (
        <Card className="max-w-xl space-y-3">
          <h2 className="font-semibold">New shortlist</h2>
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
            <div className="space-y-1">
              <label
                htmlFor="description"
                className="block text-sm font-medium"
              >
                Description
              </label>
              <textarea
                id="description"
                rows={2}
                className={select}
                {...register("description")}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="priority" className="block text-sm font-medium">
                Priority
              </label>
              <select
                id="priority"
                className={select}
                {...register("priority")}
              >
                {PRIORITIES.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
            <ErrorText>{formError}</ErrorText>
            <Button type="submit" disabled={isSubmitting}>
              Create shortlist
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
