"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button, Card, Empty, ErrorText, Stat } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import {
  POSITION_GROUPS,
  type Page,
  type PlayerSummary,
  type Squad,
  type Team,
} from "@/lib/types";

const input =
  "rounded-[2px] border border-line-strong bg-transparent px-2 py-1 text-sm";

export default function TeamPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId, can } = useAuth();
  const qc = useQueryClient();
  const manage = can("clubs:manage");
  const [group, setGroup] = useState("");
  const [showLeft, setShowLeft] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [number, setNumber] = useState("");

  const squad = useQuery({
    queryKey: ["squad", activeOrgId, id, group, showLeft],
    queryFn: () =>
      apiFetch<Squad>(
        `/teams/${id}/squad?include_left=${showLeft}${group ? `&group=${group}` : ""}`,
      ),
    enabled: !!activeOrgId,
  });
  const candidates = useQuery({
    queryKey: ["squad-candidates", activeOrgId, search],
    queryFn: () =>
      apiFetch<Page<PlayerSummary>>(
        `/players?q=${encodeURIComponent(search)}&page_size=6`,
      ),
    enabled: !!activeOrgId && manage && search.trim().length >= 2,
  });
  const otherTeams = useQuery({
    queryKey: ["teams", activeOrgId],
    queryFn: () => apiFetch<Team[]>("/teams"),
    enabled: !!activeOrgId && manage,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["squad", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["teams"] });
    qc.invalidateQueries({ queryKey: ["players"] });
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

  if (squad.isLoading) return <p aria-busy="true">Loading…</p>;
  if (squad.error || !squad.data) {
    return (
      <div className="space-y-2">
        <ErrorText>{squad.error?.message ?? "Team not found"}</ErrorText>
        <Link href="/teams" className="text-sm text-link underline">
          Back to teams
        </Link>
      </div>
    );
  }
  const { team, players, counts_by_group: counts } = squad.data;

  return (
    <div className="space-y-6">
      <Link href="/teams" className="text-sm text-link underline">
        ← Teams
      </Link>
      <header>
        <h1 className="text-2xl font-bold">{team.name}</h1>
        <p className="text-sm opacity-70">
          {team.club_name} · {team.team_type} · {team.active_players} active
          players
        </p>
      </header>
      <ErrorText>{error}</ErrorText>

      <section
        className="grid grid-cols-2 gap-3 sm:grid-cols-4"
        aria-label="Squad composition"
      >
        {Object.keys(POSITION_GROUPS).map((g) => (
          <Stat key={g} label={g} value={counts[g] ?? 0} />
        ))}
      </section>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label>
          Position{" "}
          <select
            value={group}
            onChange={(e) => setGroup(e.target.value)}
            className={input}
          >
            <option value="">All</option>
            {Object.keys(POSITION_GROUPS).map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={showLeft}
            onChange={(e) => setShowLeft(e.target.checked)}
          />{" "}
          Include former players
        </label>
      </div>

      {players.length === 0 ? (
        <Empty>No players in this squad.</Empty>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line text-xs uppercase opacity-60">
            <tr>
              <th className="py-2">No.</th>
              <th>Player</th>
              <th>Pos</th>
              <th>Age</th>
              <th>Since</th>
              {manage && <th className="text-right">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {players.map((p) => (
              <tr
                key={p.membership_id}
                className={`border-b border-line-soft ${p.status === "left" ? "opacity-50" : ""}`}
              >
                <td className="py-2">{p.squad_number ?? "—"}</td>
                <td>
                  <Link
                    href={`/players/${p.player_id}`}
                    className="font-medium text-link hover:underline"
                  >
                    {p.full_name}
                  </Link>
                  {p.is_minor && (
                    <span className="ml-2 rounded bg-warn-soft px-1.5 text-xs text-warn">
                      U18
                    </span>
                  )}
                </td>
                <td>{p.position ?? p.primary_position ?? "—"}</td>
                <td>{p.age}</td>
                <td>
                  {p.registered_on}
                  {p.left_on ? ` → ${p.left_on}` : ""}
                </td>
                {manage && (
                  <td className="space-x-2 text-right">
                    {p.status === "active" && (
                      <>
                        <select
                          aria-label={`Move ${p.full_name} to another team`}
                          value=""
                          onChange={(e) =>
                            e.target.value &&
                            run(() =>
                              apiFetch(
                                `/teams/${id}/players/${p.membership_id}/transfer`,
                                {
                                  method: "POST",
                                  json: { to_team_id: e.target.value },
                                },
                              ),
                            )
                          }
                          className={input}
                        >
                          <option value="">Move to…</option>
                          {otherTeams.data
                            ?.filter((t) => t.id !== id)
                            .map((t) => (
                              <option key={t.id} value={t.id}>
                                {t.club_name} — {t.name}
                              </option>
                            ))}
                        </select>
                        <Button
                          variant="danger"
                          onClick={() => {
                            if (
                              window.confirm(
                                `Release ${p.full_name} from ${team.name}?`,
                              )
                            )
                              run(() =>
                                apiFetch(
                                  `/teams/${id}/players/${p.membership_id}`,
                                  { method: "DELETE" },
                                ),
                              );
                          }}
                        >
                          Release
                        </Button>
                      </>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {manage && (
        <Card className="max-w-xl space-y-3">
          <h2 className="font-semibold">Add a player</h2>
          <div className="flex gap-2">
            <input
              type="search"
              aria-label="Search players to add"
              placeholder="Search by name (2+ letters)…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={`${input} flex-1`}
            />
            <input
              aria-label="Squad number"
              inputMode="numeric"
              placeholder="No."
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              className={`${input} w-20`}
            />
          </div>
          <ul className="space-y-1 text-sm">
            {candidates.data?.items.map((c) => (
              <li key={c.id} className="flex items-center justify-between">
                <span>
                  {c.full_name}{" "}
                  <span className="opacity-60">
                    · {c.age} · {c.primary_position ?? "—"}
                  </span>
                </span>
                <Button
                  variant="secondary"
                  onClick={() =>
                    run(async () => {
                      await apiFetch(`/teams/${id}/players`, {
                        method: "POST",
                        json: {
                          player_id: c.id,
                          squad_number: number ? Number(number) : null,
                        },
                      });
                      setSearch("");
                      setNumber("");
                    })
                  }
                >
                  Add
                </Button>
              </li>
            ))}
            {candidates.data && candidates.data.items.length === 0 && (
              <li className="opacity-60">No matching players.</li>
            )}
          </ul>
        </Card>
      )}
    </div>
  );
}
