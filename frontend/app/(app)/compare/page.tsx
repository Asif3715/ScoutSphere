"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { PlayerAvatar } from "@/components/players/player-avatar";
import { Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import {
  label,
  type CompareResult,
  type Page,
  type RequirementSummary,
} from "@/lib/types";

function dash(v: string | number | null | undefined) {
  return v == null || v === "" ? "—" : String(v);
}

function Compare() {
  const { activeOrgId } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const ids = (params.get("ids") ?? "").split(",").filter(Boolean);
  const requirementId = params.get("requirement_id") ?? "";

  const result = useQuery({
    queryKey: ["compare", activeOrgId, ids.join(","), requirementId],
    queryFn: () =>
      apiFetch<CompareResult>("/recruitment/compare", {
        method: "POST",
        json: { player_ids: ids, requirement_id: requirementId || null },
      }),
    enabled: !!activeOrgId && ids.length >= 2,
  });
  const reqs = useQuery({
    queryKey: ["requirements", activeOrgId, "options"],
    queryFn: () =>
      apiFetch<Page<RequirementSummary>>(
        "/recruitment/requirements?page_size=100",
      ),
    enabled: !!activeOrgId,
  });

  if (ids.length < 2) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Compare players</h1>
        <p className="text-sm">
          Choose 2 to 5 players from{" "}
          <Link className="text-link underline" href="/recruitment/search">
            Find players
          </Link>{" "}
          or from a shortlist.
        </p>
      </div>
    );
  }
  const data = result.data;
  const rows: [string, (p: CompareResult["players"][number]) => string][] = [
    ["Age", (p) => dash(p.player.age)],
    [
      "Position",
      (p) =>
        [p.player.primary_position, ...p.secondary_positions]
          .filter(Boolean)
          .join(", ") || "—",
    ],
    ["Nationality", (p) => dash(p.player.nationality)],
    ["Preferred foot", (p) => dash(p.preferred_foot)],
    [
      "Height / weight",
      (p) =>
        `${p.height_cm ? p.height_cm + " cm" : "—"} / ${p.weight_kg ? p.weight_kg + " kg" : "—"}`,
    ],
    ["Current club", (p) => dash(p.player.current_club?.club_name)],
    ["Contract", (p) => dash(p.objective.contract_status ?? "not tracked yet")],
  ];
  const objective: [string, (p: CompareResult["players"][number]) => string][] =
    [
      ["Career appearances", (p) => dash(p.objective.appearances)],
      ["Career goals", (p) => dash(p.objective.goals)],
      ["Career assists", (p) => dash(p.objective.assists)],
      ["Most recent club", (p) => dash(p.objective.recent_club)],
      ["…appearances there", (p) => dash(p.objective.recent_appearances)],
      ["…goals there", (p) => dash(p.objective.recent_goals)],
      ["…assists there", (p) => dash(p.objective.recent_assists)],
    ];

  const table = (title: string, note: string | null, body: React.ReactNode) => (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      {note && <p className="text-xs opacity-60">{note}</p>}
      <div className="overflow-x-auto">{body}</div>
    </section>
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Compare players</h1>
        <label className="text-sm">
          Judge against a requirement{" "}
          <select
            value={requirementId}
            onChange={(e) =>
              router.replace(
                `/compare?ids=${ids.join(",")}${e.target.value ? `&requirement_id=${e.target.value}` : ""}`,
              )
            }
            className="rounded-[2px] border border-line-strong bg-transparent px-2 py-1"
          >
            <option value="">None</option>
            {reqs.data?.items.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
      </header>
      {result.isLoading && <p aria-busy="true">Comparing…</p>}
      <ErrorText>{result.error?.message}</ErrorText>
      {data && (
        <>
          {table(
            "Profile",
            null,
            <table className="w-full min-w-[40rem] table-fixed text-left text-sm">
              <thead className="border-b border-line text-xs uppercase opacity-60">
                <tr>
                  <th className="w-44 py-2"></th>
                  {data.players.map((p) => (
                    <th key={p.player.id} className="pb-2 align-bottom">
                      <PlayerAvatar
                        name={p.player.full_name}
                        src={p.player.photo_thumb_url}
                        size="md"
                        className="mb-2 block"
                      />
                      <Link
                        href={`/players/${p.player.id}`}
                        className="text-link hover:underline"
                      >
                        {p.player.full_name}
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(([name, fn]) => (
                  <tr key={name} className="border-b border-line-soft">
                    <th className="w-44 py-1 pr-4 text-left font-normal opacity-70">
                      {name}
                    </th>
                    {data.players.map((p) => (
                      <td key={p.player.id}>{fn(p)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>,
          )}
          {table(
            "Objective statistics",
            "Recorded facts only. Nothing here comes from a scout's opinion. A dash means no data is recorded.",
            <table className="w-full min-w-[40rem] table-fixed text-left text-sm">
              <tbody>
                {objective.map(([name, fn]) => (
                  <tr key={name} className="border-b border-line-soft">
                    <th className="w-44 py-1 pr-4 text-left font-normal opacity-70">
                      {name}
                    </th>
                    {data.players.map((p) => (
                      <td key={p.player.id}>{fn(p)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>,
          )}
          {table(
            "Scout evaluations",
            "Subjective. Averages over your organization's approved reports only. A highlighted value is the highest in its row; ties are all highlighted. There is no overall score.",
            <table className="w-full min-w-[40rem] table-fixed text-left text-sm">
              <tbody>
                <tr className="border-b border-line-soft">
                  <th className="w-44 py-1 pr-4 text-left font-normal opacity-70">
                    Approved reports
                  </th>
                  {data.players.map((p) => (
                    <td key={p.player.id}>{p.scouting.approved_reports}</td>
                  ))}
                </tr>
                <tr className="border-b border-line-soft">
                  <th className="w-44 py-1 pr-4 text-left font-normal opacity-70">
                    Latest recommendation
                  </th>
                  {data.players.map((p) => (
                    <td key={p.player.id}>
                      {p.scouting.latest_recommendation
                        ? label(p.scouting.latest_recommendation)
                        : "—"}
                    </td>
                  ))}
                </tr>
                {data.attributes.map((a) => (
                  <tr key={a} className="border-b border-line-soft">
                    <th className="w-44 py-1 pr-4 text-left font-normal capitalize opacity-70">
                      {label(a)}
                    </th>
                    {data.players.map((p) => {
                      const v = p.scouting.ratings[a];
                      const best = data.leaders[a]?.includes(p.player.id);
                      return (
                        <td
                          key={p.player.id}
                          className={best ? "font-bold text-link" : ""}
                        >
                          {v == null ? "—" : v.toFixed(1)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>,
          )}
          {data.players.every((p) => p.scouting.approved_reports === 0) && (
            <p className="text-sm opacity-70">
              None of these players has an approved scouting report from your
              organization yet.
            </p>
          )}
          {data.players[0]?.suitability && (
            <section className="space-y-2">
              <h2 className="text-lg font-semibold">
                Suitability for “{data.requirement_title}”
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {data.players.map((p) => (
                  <Card key={p.player.id} className="space-y-1 text-sm">
                    <p className="font-semibold">{p.player.full_name}</p>
                    <ul className="space-y-0.5 text-xs">
                      {p.suitability!.map((c) => (
                        <li
                          key={c.name}
                          className={c.met ? "text-ok" : "text-bad"}
                        >
                          {c.met ? "✓" : "✗"} {c.name}: {c.actual ?? "no data"}{" "}
                          <span className="opacity-60">
                            (need {c.required})
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<p aria-busy="true">Loading…</p>}>
      <Compare />
    </Suspense>
  );
}
