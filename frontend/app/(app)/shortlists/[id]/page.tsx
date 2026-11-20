"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import {
  PRIORITIES,
  ROLE_LABELS,
  label,
  type Member,
  type Page,
  type PlayerSummary,
  type ShortlistDetail,
} from "@/lib/types";

const input =
  "rounded-[2px] border border-line-strong bg-transparent px-2 py-1 text-sm";
// roles that have recruitment access and so can be given a shared shortlist
const CAN_SHARE_WITH = [
  "club_owner",
  "club_admin",
  "recruitment_manager",
  "coach",
];

export default function ShortlistPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId, user, can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sharing, setSharing] = useState(false);
  const [picked, setPicked] = useState<string[] | null>(null);

  const sl = useQuery({
    queryKey: ["shortlist", activeOrgId, id],
    queryFn: () => apiFetch<ShortlistDetail>(`/recruitment/shortlists/${id}`),
    enabled: !!activeOrgId,
  });
  const candidates = useQuery({
    queryKey: ["players", activeOrgId, "shortlist-search", search],
    queryFn: () =>
      apiFetch<Page<PlayerSummary>>(
        `/players?q=${encodeURIComponent(search)}&page_size=6`,
      ),
    enabled: !!activeOrgId && search.trim().length >= 2,
  });
  const members = useQuery({
    queryKey: ["members", activeOrgId],
    queryFn: () => apiFetch<Member[]>(`/organizations/${activeOrgId}/members`),
    enabled: !!activeOrgId && sharing && can("members:read"),
  });

  if (sl.isLoading) return <p aria-busy="true">Loading…</p>;
  if (sl.error || !sl.data) {
    return (
      <div className="space-y-2">
        <ErrorText>{sl.error?.message ?? "Shortlist not found"}</ErrorText>
        <Link href="/shortlists" className="text-sm text-link underline">
          Back to shortlists
        </Link>
      </div>
    );
  }
  const s = sl.data;
  const owner = s.is_owner && can("recruitment:manage");
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["shortlist", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["shortlists"] });
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
  const base = `/recruitment/shortlists/${id}`;
  const onList = new Set(s.players.map((p) => p.player.id));
  const shareable =
    members.data?.filter(
      (m) => CAN_SHARE_WITH.includes(m.role) && m.user_id !== user?.id,
    ) ?? [];
  const current = picked ?? s.shared_with.map((x) => x.user_id);

  return (
    <div className="space-y-5">
      <Link href="/shortlists" className="text-sm text-link underline">
        ← Shortlists
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{s.name}</h1>
          <p className="text-sm opacity-70">
            priority {s.priority}
            {s.requirement_title ? ` · for ${s.requirement_title}` : ""} ·{" "}
            {s.is_owner ? "created by you" : `shared by ${s.owner_name}`}
          </p>
          {s.description && <p className="mt-1 text-sm">{s.description}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {s.players.length >= 2 && s.players.length <= 5 && (
            <Button
              onClick={() =>
                router.push(
                  `/compare?ids=${s.players.map((p) => p.player.id).join(",")}`,
                )
              }
            >
              Compare players
            </Button>
          )}
          {owner && (
            <>
              <Button variant="secondary" onClick={() => setSharing((x) => !x)}>
                Share
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  if (
                    !window.confirm(
                      `Delete “${s.name}”? The players themselves are not affected.`,
                    )
                  )
                    return;
                  run(async () => {
                    await apiFetch(base, { method: "DELETE" });
                    router.replace("/shortlists");
                  });
                }}
              >
                Delete
              </Button>
            </>
          )}
        </div>
      </header>
      <ErrorText>{error}</ErrorText>
      {s.players.length > 5 && (
        <p className="text-xs opacity-60">
          Comparison supports up to 5 players at a time.
        </p>
      )}

      {owner && sharing && (
        <Card className="space-y-2 text-sm">
          <h2 className="font-semibold">Share with colleagues (view only)</h2>
          {shareable.length === 0 && (
            <p className="opacity-70">
              No colleagues with recruitment access to share with.
            </p>
          )}
          {shareable.map((m) => (
            <label key={m.user_id} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={current.includes(m.user_id)}
                onChange={(e) =>
                  setPicked(
                    e.target.checked
                      ? [...current, m.user_id]
                      : current.filter((x) => x !== m.user_id),
                  )
                }
              />
              {m.full_name}{" "}
              <span className="text-xs opacity-60">
                {ROLE_LABELS[m.role] ?? m.role}
              </span>
            </label>
          ))}
          <Button
            onClick={() =>
              run(async () => {
                await apiFetch(`${base}/shares`, {
                  method: "PUT",
                  json: { user_ids: current },
                });
                setPicked(null);
                setSharing(false);
              })
            }
          >
            Save sharing
          </Button>
        </Card>
      )}
      {owner && s.shared_with.length > 0 && !sharing && (
        <p className="text-xs opacity-70">
          Shared with: {s.shared_with.map((x) => x.full_name).join(", ")}
        </p>
      )}

      {s.players.length === 0 ? (
        <Empty>No players yet.</Empty>
      ) : (
        <ul className="space-y-2">
          {s.players.map((e) => (
            <li
              key={e.player.id}
              className="rounded-[2px] border border-line p-3 text-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <Link
                    href={`/players/${e.player.id}`}
                    className="font-medium text-link hover:underline"
                  >
                    {e.player.full_name}
                  </Link>{" "}
                  <span className="opacity-60">
                    {e.player.age} · {e.player.primary_position ?? "—"} ·{" "}
                    {e.player.current_club?.club_name ?? "no club"}
                  </span>
                  {e.pipeline.map((p) => (
                    <Link
                      key={p.requirement_id}
                      href={`/recruitment/${p.requirement_id}`}
                      className="ml-2 rounded bg-info-soft px-1.5 text-xs text-info"
                    >
                      {p.requirement_title}: {label(p.stage)}
                    </Link>
                  ))}
                </div>
                {owner ? (
                  <div className="flex items-center gap-2">
                    <select
                      aria-label={`Priority for ${e.player.full_name}`}
                      value={e.priority}
                      onChange={(ev) =>
                        run(() =>
                          apiFetch(`${base}/players/${e.player.id}`, {
                            method: "PATCH",
                            json: { priority: ev.target.value },
                          }),
                        )
                      }
                      className={input}
                    >
                      {PRIORITIES.map((p) => (
                        <option key={p}>{p}</option>
                      ))}
                    </select>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        run(() =>
                          apiFetch(`${base}/players/${e.player.id}`, {
                            method: "DELETE",
                          }),
                        )
                      }
                    >
                      Remove
                    </Button>
                  </div>
                ) : (
                  <span className="text-xs opacity-60">
                    priority {e.priority}
                  </span>
                )}
              </div>
              {owner ? (
                <input
                  aria-label={`Notes for ${e.player.full_name}`}
                  defaultValue={e.notes ?? ""}
                  placeholder="Internal notes…"
                  onBlur={(ev) =>
                    ev.target.value !== (e.notes ?? "") &&
                    run(() =>
                      apiFetch(`${base}/players/${e.player.id}`, {
                        method: "PATCH",
                        json: { notes: ev.target.value || null },
                      }),
                    )
                  }
                  className={`${input} mt-2 w-full`}
                />
              ) : (
                e.notes && <p className="mt-1 text-xs opacity-80">{e.notes}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {owner && (
        <Card className="max-w-xl space-y-2">
          <h2 className="font-semibold">Add a player</h2>
          <input
            type="search"
            aria-label="Search players to add"
            placeholder="Search by name (2+ letters)…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`${input} w-full`}
          />
          <ul className="space-y-1 text-sm">
            {candidates.data?.items
              .filter((c) => !onList.has(c.id))
              .map((c) => (
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
                        await apiFetch(`${base}/players`, {
                          method: "POST",
                          json: { player_id: c.id },
                        });
                        setSearch("");
                      })
                    }
                  >
                    Add
                  </Button>
                </li>
              ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
