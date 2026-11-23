"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { PhotoEditor } from "@/components/players/photo-editor";
import { PlayerAvatar } from "@/components/players/player-avatar";
import { PlayerForm } from "@/components/players/player-form";
import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import {
  careerSchema,
  mediaSchema,
  type CareerValues,
  type MediaValues,
} from "@/lib/schemas";
import {
  MEDIA_KINDS,
  SPELL_TYPES,
  VISIBILITY_LABELS,
  type Career,
  type Club,
  type Media,
  type Page,
  type Player,
} from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

export default function PlayerPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId, can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const enabled = !!activeOrgId;

  const player = useQuery({
    queryKey: ["player", activeOrgId, id],
    queryFn: () => apiFetch<Player>(`/players/${id}`),
    enabled,
  });
  const career = useQuery({
    queryKey: ["career", activeOrgId, id],
    queryFn: () => apiFetch<Career[]>(`/players/${id}/career`),
    enabled,
  });
  const media = useQuery({
    queryKey: ["media", activeOrgId, id],
    queryFn: () => apiFetch<Media[]>(`/players/${id}/media`),
    enabled,
  });

  if (player.isLoading) return <p aria-busy="true">Loading…</p>;
  if (player.error || !player.data) {
    return (
      <div className="space-y-2">
        <ErrorText>{player.error?.message ?? "Player not found"}</ErrorText>
        <Link href="/players" className="text-sm text-link underline">
          Back to players
        </Link>
      </div>
    );
  }
  const p = player.data;
  const canEdit = can("players:write") && p.is_owner;
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["player", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["career", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["media", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["players"] });
  };
  const fail = (e: unknown) =>
    setActionError(e instanceof ApiError ? e.message : "Request failed");

  async function archive() {
    if (
      !window.confirm(
        `Archive ${p.full_name}? They will disappear from player searches.`,
      )
    )
      return;
    try {
      await apiFetch(`/players/${id}`, { method: "DELETE" });
      await qc.invalidateQueries({ queryKey: ["players"] });
      router.replace("/players");
    } catch (e) {
      fail(e);
    }
  }

  return (
    <div className="space-y-6">
      <Link href="/players" className="text-sm text-link underline">
        ← Players
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-5">
          <PlayerAvatar name={p.full_name} src={p.photo_url} size="xl" />
          <div>
            <h1 className="text-2xl font-bold">
              {p.full_name}
              {p.is_minor && (
                <span className="ml-2 rounded bg-warn-soft px-2 py-0.5 text-xs font-medium text-warn">
                  Under 18
                </span>
              )}
              {p.claimed && (
                <span
                  className="chip ml-2 bg-ok-soft align-middle text-ok"
                  title="This player has their own account"
                >
                  Has account
                </span>
              )}
              {p.open_to_offers && (
                <span className="chip ml-2 bg-volt/40 align-middle text-ink">
                  Open to offers
                </span>
              )}
            </h1>
            <p className="text-sm opacity-70">
              {[
                p.age + " years",
                p.primary_position,
                p.nationality,
                p.current_club?.club_name,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {p.contact_email && (
              <p className="text-sm">
                Contact:{" "}
                <a
                  href={`mailto:${p.contact_email}`}
                  className="text-link underline"
                >
                  {p.contact_email}
                </a>
              </p>
            )}
            <p className="text-xs opacity-60">
              {p.is_owner
                ? p.claimed
                  ? "Visibility is set by the player"
                  : VISIBILITY_LABELS[p.visibility]
                : "Shared with your organization by another club (read-only)"}
            </p>
            {p.is_minor && !p.is_owner && (
              <p className="mt-1 text-xs opacity-60">
                Photos of under-18 players are only visible to the club that
                added them.
              </p>
            )}
          </div>
        </div>
        {canEdit && !editing && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button variant="danger" onClick={archive}>
              Archive
            </Button>
          </div>
        )}
      </header>
      <ErrorText>{actionError}</ErrorText>
      {canEdit && !editing && (
        <Card className="space-y-3">
          <h2>Photo</h2>
          <PhotoEditor
            name={p.full_name}
            current={p.photo_url}
            onSave={async (file, crop) => {
              const body = new FormData();
              body.append("file", file);
              body.append("crop_x", String(crop.x));
              body.append("crop_y", String(crop.y));
              body.append("crop_size", String(crop.size));
              await apiFetch(`/players/${id}/photo`, { method: "PUT", body });
              refresh();
            }}
            onRemove={async () => {
              await apiFetch(`/players/${id}/photo`, { method: "DELETE" });
              refresh();
            }}
          />
        </Card>
      )}

      {editing ? (
        <PlayerForm
          player={p}
          submitLabel="Save changes"
          onSubmit={async (payload) => {
            await apiFetch(`/players/${id}`, {
              method: "PATCH",
              json: payload,
            });
            refresh();
            setEditing(false);
          }}
        />
      ) : (
        <Card>
          <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
            {(
              [
                ["Date of birth", p.date_of_birth],
                ["Height", p.height_cm ? `${p.height_cm} cm` : null],
                ["Weight", p.weight_kg ? `${p.weight_kg} kg` : null],
                ["Preferred foot", p.preferred_foot],
                ["Primary position", p.primary_position],
                ["Other positions", p.secondary_positions.join(", ") || null],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="opacity-60">{label}</dt>
                <dd>{value ?? "—"}</dd>
              </div>
            ))}
          </dl>
          {p.biography ? (
            <p className="mt-4 whitespace-pre-wrap text-sm">{p.biography}</p>
          ) : (
            p.is_minor &&
            !p.is_owner && (
              <p className="mt-4 text-xs opacity-60">
                Biography and photo are hidden for players under 18.
              </p>
            )
          )}
        </Card>
      )}

      <CareerSection
        entries={career.data ?? []}
        playerId={id}
        canAdd={canEdit}
        onChange={refresh}
        onError={fail}
      />
      <MediaSection
        items={media.data ?? []}
        playerId={id}
        canAdd={can("players:write")}
        onChange={refresh}
        onError={fail}
      />
    </div>
  );
}

function CareerSection({
  entries,
  playerId,
  canAdd,
  onChange,
  onError,
}: {
  entries: Career[];
  playerId: string;
  canAdd: boolean;
  onChange: () => void;
  onError: (e: unknown) => void;
}) {
  const { activeOrgId } = useAuth();
  const [adding, setAdding] = useState(false);
  const clubs = useQuery({
    queryKey: ["club-options", activeOrgId],
    queryFn: async () => {
      const [mine, ref] = await Promise.all([
        apiFetch<Page<Club>>("/clubs?scope=mine&page_size=100"),
        apiFetch<Page<Club>>("/clubs?scope=reference&page_size=100"),
      ]);
      return [...mine.items, ...ref.items];
    },
    enabled: adding,
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CareerValues>({
    resolver: zodResolver(careerSchema),
    defaultValues: { spell_type: "permanent" },
  });

  const submit = handleSubmit(async (v) => {
    const num = (s?: string) => (s && s !== "" ? Number(s) : null);
    try {
      await apiFetch(`/players/${playerId}/career`, {
        method: "POST",
        json: {
          club_id: v.club_id,
          team_label: v.team_label || null,
          spell_type: v.spell_type,
          start_date: v.start_date,
          end_date: v.end_date || null,
          appearances: num(v.appearances),
          goals: num(v.goals),
          assists: num(v.assists),
        },
      });
      reset({ spell_type: "permanent" });
      setAdding(false);
      onChange();
    } catch (e) {
      onError(e);
    }
  });

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Career history</h2>
        {canAdd && !adding && (
          <Button variant="secondary" onClick={() => setAdding(true)}>
            Add spell
          </Button>
        )}
      </div>
      {adding && (
        <Card>
          <form
            onSubmit={submit}
            className="grid max-w-2xl grid-cols-2 gap-4"
            noValidate
          >
            <div className="col-span-2 space-y-1">
              <label htmlFor="club_id" className="block text-sm font-medium">
                Club
              </label>
              <select id="club_id" className={select} {...register("club_id")}>
                <option value="">Choose…</option>
                {clubs.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.is_reference ? " (reference)" : ""}
                  </option>
                ))}
              </select>
              <ErrorText>{errors.club_id?.message}</ErrorText>
            </div>
            <Field label="Team (e.g. U19)" {...register("team_label")} />
            <div className="space-y-1">
              <label htmlFor="spell_type" className="block text-sm font-medium">
                Type
              </label>
              <select
                id="spell_type"
                className={select}
                {...register("spell_type")}
              >
                {SPELL_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <Field
              label="From"
              type="date"
              error={errors.start_date?.message}
              {...register("start_date")}
            />
            <Field
              label="To (blank = current)"
              type="date"
              error={errors.end_date?.message}
              {...register("end_date")}
            />
            <Field
              label="Appearances"
              inputMode="numeric"
              error={errors.appearances?.message}
              {...register("appearances")}
            />
            <Field
              label="Goals"
              inputMode="numeric"
              error={errors.goals?.message}
              {...register("goals")}
            />
            <Field
              label="Assists"
              inputMode="numeric"
              error={errors.assists?.message}
              {...register("assists")}
            />
            <div className="col-span-2 flex gap-2">
              <Button type="submit" disabled={isSubmitting}>
                Save spell
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setAdding(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}
      {entries.length === 0 ? (
        <Empty>No career history recorded.</Empty>
      ) : (
        <ol className="space-y-2">
          {entries.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between rounded-[2px] border border-line px-3 py-2 text-sm"
            >
              <div>
                <p className="font-medium">
                  {e.club_name}
                  {e.team_label ? ` · ${e.team_label}` : ""}{" "}
                  <span className="text-xs font-normal opacity-60">
                    {e.spell_type}
                  </span>
                </p>
                <p className="text-xs opacity-70">
                  {e.start_date} → {e.end_date ?? "present"}
                  {e.appearances != null ? ` · ${e.appearances} apps` : ""}
                  {e.goals != null ? ` · ${e.goals} goals` : ""}
                  {e.assists != null ? ` · ${e.assists} assists` : ""}
                </p>
              </div>
              {e.editable && !e.managed_by_squad && (
                <Button
                  variant="danger"
                  onClick={async () => {
                    if (!window.confirm("Delete this career entry?")) return;
                    try {
                      await apiFetch(`/players/${playerId}/career/${e.id}`, {
                        method: "DELETE",
                      });
                      onChange();
                    } catch (err) {
                      onError(err);
                    }
                  }}
                >
                  Delete
                </Button>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function MediaSection({
  items,
  playerId,
  canAdd,
  onChange,
  onError,
}: {
  items: Media[];
  playerId: string;
  canAdd: boolean;
  onChange: () => void;
  onError: (e: unknown) => void;
}) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<MediaValues>({
    resolver: zodResolver(mediaSchema),
    defaultValues: { kind: "video" },
  });

  const submit = handleSubmit(async (v) => {
    try {
      await apiFetch(`/players/${playerId}/media`, { method: "POST", json: v });
      reset({ kind: v.kind, title: "", url: "" });
      onChange();
    } catch (e) {
      onError(e);
    }
  });

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Videos and documents</h2>
      <p className="text-xs opacity-60">
        Links you add here are visible only to your organization.
      </p>
      {items.length === 0 ? (
        <Empty>No links yet.</Empty>
      ) : (
        <ul className="space-y-2">
          {items.map((m) => (
            <li
              key={m.id}
              className="flex items-center justify-between rounded-[2px] border border-line px-3 py-2 text-sm"
            >
              <a
                href={m.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-link hover:underline"
              >
                {m.title} <span className="text-xs opacity-60">({m.kind})</span>
              </a>
              {canAdd && (
                <Button
                  variant="secondary"
                  onClick={async () => {
                    try {
                      await apiFetch(`/players/${playerId}/media/${m.id}`, {
                        method: "DELETE",
                      });
                      onChange();
                    } catch (e) {
                      onError(e);
                    }
                  }}
                >
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canAdd && (
        <form
          onSubmit={submit}
          className="grid max-w-2xl grid-cols-[8rem_1fr_1fr_auto] items-start gap-3"
          noValidate
        >
          <select aria-label="Kind" className={select} {...register("kind")}>
            {MEDIA_KINDS.map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
          <div>
            <input
              aria-label="Title"
              placeholder="Title"
              className={select}
              {...register("title")}
            />
            <ErrorText>{errors.title?.message}</ErrorText>
          </div>
          <div>
            <input
              aria-label="URL"
              placeholder="https://…"
              className={select}
              {...register("url")}
            />
            <ErrorText>{errors.url?.message}</ErrorText>
          </div>
          <Button type="submit" disabled={isSubmitting}>
            Add
          </Button>
        </form>
      )}
    </section>
  );
}
