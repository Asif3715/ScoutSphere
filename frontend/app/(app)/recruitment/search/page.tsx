"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PlayerAvatar } from "@/components/players/player-avatar";
import { Button, Card, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { fetchAll } from "@/lib/fetch-all";
import { ratingFilters } from "@/lib/schemas";
import {
  FEET,
  POSITIONS,
  RATING_GROUPS,
  label,
  type CandidateMatch,
  type Page,
  type ShortlistSummary,
} from "@/lib/types";

const input =
  "rounded-[2px] border border-line-strong bg-transparent px-3 py-1.5 text-sm";
const EMPTY = {
  q: "",
  position: "",
  min_age: "",
  max_age: "",
  nationality: "",
  foot: "",
  min_appearances: "",
};

export default function SearchPage() {
  const { activeOrgId, can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [f, setF] = useState(EMPTY);
  const [ratings, setRatings] = useState<Record<string, string>>({});
  const [applied, setApplied] = useState<{
    f: typeof EMPTY;
    ratings: Record<string, string>;
  } | null>(null);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [shortlistId, setShortlistId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const results = useQuery({
    queryKey: ["recruitment-search", activeOrgId, applied, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "10",
      });
      for (const [k, v] of Object.entries(applied!.f)) if (v) params.set(k, v);
      for (const r of ratingFilters(applied!.ratings))
        params.append("min_rating", r);
      return apiFetch<Page<CandidateMatch>>(`/recruitment/search?${params}`);
    },
    enabled: !!activeOrgId && !!applied,
  });
  const shortlists = useQuery({
    queryKey: ["shortlists", activeOrgId, "mine-options"],
    queryFn: () =>
      fetchAll<ShortlistSummary>("/recruitment/shortlists?scope=mine"),
    enabled: !!activeOrgId && can("recruitment:manage"),
  });

  const set =
    (k: keyof typeof EMPTY) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setF((s) => ({ ...s, [k]: e.target.value }));
  const toggle = (id: string, on: boolean) =>
    setSelected((s) =>
      on ? (s.length < 5 ? [...s, id] : s) : s.filter((x) => x !== id),
    );

  async function addToShortlist() {
    setError(null);
    setMessage(null);
    let added = 0;
    for (const id of selected) {
      try {
        await apiFetch(`/recruitment/shortlists/${shortlistId}/players`, {
          method: "POST",
          json: { player_id: id },
        });
        added++;
      } catch (e) {
        if (!(e instanceof ApiError && e.code === "already_shortlisted")) {
          setError(e instanceof ApiError ? e.message : "Request failed");
          return;
        }
      }
    }
    setMessage(
      `${added} player${added === 1 ? "" : "s"} added to the shortlist.`,
    );
    setSelected([]);
    qc.invalidateQueries({ queryKey: ["shortlists"] });
  }

  return (
    <div className="space-y-4">
      <Link href="/recruitment" className="text-sm text-link underline">
        ← Recruitment
      </Link>
      <h1 className="text-2xl font-bold">Find players</h1>
      <Card className="space-y-3">
        <form
          method="post"
          onSubmit={(e) => {
            e.preventDefault();
            setApplied({ f, ratings });
            setPage(1);
            setSelected([]);
          }}
          className="space-y-3"
        >
          <div className="flex flex-wrap items-end gap-3">
            <input
              type="search"
              aria-label="Search by name"
              placeholder="Name…"
              value={f.q}
              onChange={set("q")}
              className={input}
            />
            <label className="text-xs">
              Position
              <select
                value={f.position}
                onChange={set("position")}
                className={`${input} block`}
              >
                <option value="">Any</option>
                {POSITIONS.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              Min age
              <input
                inputMode="numeric"
                value={f.min_age}
                onChange={set("min_age")}
                className={`${input} block w-20`}
              />
            </label>
            <label className="text-xs">
              Max age
              <input
                inputMode="numeric"
                value={f.max_age}
                onChange={set("max_age")}
                className={`${input} block w-20`}
              />
            </label>
            <label className="text-xs">
              Nationality
              <input
                value={f.nationality}
                onChange={set("nationality")}
                className={`${input} block w-32`}
              />
            </label>
            <label className="text-xs">
              Foot
              <select
                value={f.foot}
                onChange={set("foot")}
                className={`${input} block`}
              >
                <option value="">Any</option>
                {FEET.map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              Min appearances
              <input
                inputMode="numeric"
                value={f.min_appearances}
                onChange={set("min_appearances")}
                className={`${input} block w-24`}
              />
            </label>
          </div>
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              Scout rating filters (average of approved reports, 1–10)
            </summary>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {Object.entries(RATING_GROUPS).map(([group, attrs]) => (
                <div key={group} className="space-y-1 text-sm">
                  <p className="text-xs font-semibold uppercase opacity-60">
                    {group}
                  </p>
                  {attrs.map((a) => (
                    <label
                      key={a}
                      className="flex items-center justify-between gap-2 capitalize"
                    >
                      {label(a)} ≥
                      <input
                        aria-label={`Minimum ${label(a)} rating`}
                        inputMode="numeric"
                        maxLength={2}
                        value={ratings[a] ?? ""}
                        onChange={(e) =>
                          setRatings((r) => ({ ...r, [a]: e.target.value }))
                        }
                        className="w-14 rounded-[2px] border border-line-strong bg-transparent px-2 py-1 text-center"
                      />
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </details>
          <div className="flex gap-2">
            <Button type="submit">Search</Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => (
                setF(EMPTY),
                setRatings({}),
                setApplied(null),
                setSelected([])
              )}
            >
              Reset
            </Button>
          </div>
        </form>
      </Card>

      <ErrorText>{error ?? results.error?.message}</ErrorText>
      {message && <p className="text-sm text-ok">{message}</p>}
      {!applied && <Empty>Set some filters and press Search.</Empty>}
      {results.isLoading && <p aria-busy="true">Searching…</p>}
      {results.data && results.data.items.length === 0 && (
        <Empty>No players match every filter.</Empty>
      )}
      {selected.length > 0 && (
        <Card className="flex flex-wrap items-center gap-2 text-sm">
          <span>{selected.length} selected (max 5)</span>
          {selected.length >= 2 && (
            <Button
              variant="secondary"
              onClick={() => router.push(`/compare?ids=${selected.join(",")}`)}
            >
              Compare
            </Button>
          )}
          {can("recruitment:manage") && (
            <>
              <select
                aria-label="Shortlist"
                value={shortlistId}
                onChange={(e) => setShortlistId(e.target.value)}
                className="rounded-[2px] border border-line-strong bg-transparent px-2 py-1"
              >
                <option value="">Add to shortlist…</option>
                {shortlists.data?.items.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <Button disabled={!shortlistId} onClick={addToShortlist}>
                Add
              </Button>
            </>
          )}
        </Card>
      )}
      <ul className="space-y-2">
        {results.data?.items.map((m) => (
          <li
            key={m.player.id}
            className="flex items-start gap-2 rounded-[2px] border border-line p-3 text-sm"
          >
            <input
              type="checkbox"
              aria-label={`Select ${m.player.full_name}`}
              className="mt-1"
              checked={selected.includes(m.player.id)}
              onChange={(e) => toggle(m.player.id, e.target.checked)}
            />
            <div>
              <PlayerAvatar
                name={m.player.full_name}
                src={m.player.photo_thumb_url}
                size="xs"
                className="mr-2 align-middle"
              />
              <Link
                href={`/players/${m.player.id}`}
                className="font-medium text-link hover:underline"
              >
                {m.player.full_name}
              </Link>{" "}
              <span className="opacity-60">
                {m.player.age} · {m.player.primary_position ?? "—"} ·{" "}
                {m.player.current_club?.club_name ?? "no club"}
              </span>
              {m.in_pipeline && (
                <span className="ml-2 rounded bg-info-soft px-1.5 text-xs text-info">
                  in a pipeline
                </span>
              )}
              <ul className="mt-1 flex flex-wrap gap-1.5 text-xs">
                {m.criteria.map((c) => (
                  <li
                    key={c.name}
                    className="rounded bg-ok-soft px-1.5 py-0.5 text-ok"
                  >
                    ✓ {c.name}: {c.actual ?? "—"}
                  </li>
                ))}
              </ul>
            </div>
          </li>
        ))}
      </ul>
      {results.data && (
        <Pagination
          page={results.data.page}
          pageSize={results.data.page_size}
          total={results.data.total}
          onChange={setPage}
        />
      )}
    </div>
  );
}
