"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import type { Club, Page, SeasonDetail } from "@/lib/types";

export default function SeasonPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId } = useAuth();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [clubId, setClubId] = useState("");

  const {
    data: season,
    error: loadError,
    isLoading,
  } = useQuery({
    queryKey: ["season", activeOrgId, id],
    queryFn: () => apiFetch<SeasonDetail>(`/seasons/${id}`),
    enabled: !!activeOrgId,
  });
  const clubs = useQuery({
    queryKey: ["club-options", activeOrgId],
    queryFn: async () => {
      const [mine, ref] = await Promise.all([
        apiFetch<Page<Club>>("/clubs?scope=mine&page_size=100"),
        apiFetch<Page<Club>>("/clubs?scope=reference&page_size=100"),
      ]);
      return [...mine.items, ...ref.items];
    },
    enabled: !!activeOrgId && !!season?.editable,
  });

  if (isLoading) return <p aria-busy="true">Loading…</p>;
  if (loadError || !season) {
    return (
      <div className="space-y-2">
        <ErrorText>{loadError?.message ?? "Season not found"}</ErrorText>
        <Link href="/competitions" className="text-sm text-link underline">
          Back to competitions
        </Link>
      </div>
    );
  }
  const inSeason = new Set(season.participants.map((p) => p.club_id));
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["season", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["competition"] });
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

  return (
    <div className="space-y-6">
      <Link
        href={`/competitions/${season.competition_id}`}
        className="text-sm text-link underline"
      >
        ← {season.competition_name}
      </Link>
      <header>
        <h1 className="text-2xl font-bold">
          {season.competition_name} · {season.name}
        </h1>
        <p className="text-sm opacity-70">
          {season.start_date} → {season.end_date} · {season.match_count} matches
          ·{" "}
          <Link
            className="text-link underline"
            href={`/matches?season_id=${season.id}`}
          >
            view matches
          </Link>
        </p>
      </header>
      <ErrorText>{error}</ErrorText>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Participating clubs</h2>
        {season.participants.length === 0 ? (
          <Empty>
            No clubs yet. Matches can only be created between participating
            clubs.
          </Empty>
        ) : (
          <ul className="space-y-2">
            {season.participants.map((p) => (
              <li
                key={p.club_id}
                className="flex items-center justify-between rounded-[2px] border border-line px-3 py-2 text-sm"
              >
                <span>
                  {p.club_name}
                  {p.is_reference && (
                    <span className="ml-2 text-xs opacity-50">reference</span>
                  )}
                </span>
                {season.editable && (
                  <Button
                    variant="secondary"
                    onClick={() =>
                      run(() =>
                        apiFetch(`/seasons/${id}/participants/${p.club_id}`, {
                          method: "DELETE",
                        }),
                      )
                    }
                  >
                    Remove
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {season.editable && (
        <Card className="max-w-xl space-y-3">
          <h2 className="font-semibold">Add a club</h2>
          <div className="flex gap-2">
            <select
              aria-label="Club to add"
              value={clubId}
              onChange={(e) => setClubId(e.target.value)}
              className="flex-1 rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm"
            >
              <option value="">Choose…</option>
              {clubs.data
                ?.filter((c) => !inSeason.has(c.id))
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.is_reference ? " (reference)" : ""}
                  </option>
                ))}
            </select>
            <Button
              disabled={!clubId}
              onClick={() =>
                run(async () => {
                  await apiFetch(`/seasons/${id}/participants`, {
                    method: "POST",
                    json: { club_id: clubId },
                  });
                  setClubId("");
                })
              }
            >
              Add
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
