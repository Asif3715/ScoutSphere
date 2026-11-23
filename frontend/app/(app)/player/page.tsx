"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PhotoEditor } from "@/components/players/photo-editor";
import { PlayerAvatar } from "@/components/players/player-avatar";
import { PositionChip } from "@/components/players/position-chip";
import { PageHeader, TableCard } from "@/components/ui/data-table";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { shortDate, timeAgo } from "@/lib/format";
import { ApiError, apiFetch } from "@/lib/http";
import {
  FEET,
  POSITIONS,
  label,
  type Claimable,
  type MyClaim,
  type SelfProfile,
} from "@/lib/types";

const KEY = ["self-profile"];
const CLAIMS = ["self-claims"];

const fieldClass = "field-input w-full";
const msg = (e: unknown) =>
  e instanceof ApiError ? e.message : "Something went wrong. Try again.";

// ---- not linked yet: find your profile and ask the club to confirm it -------------------
function ClaimFlow() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [searched, setSearched] = useState<{
    name: string;
    dob: string;
  } | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const claims = useQuery({
    queryKey: CLAIMS,
    queryFn: () => apiFetch<MyClaim[]>("/me/player/claims"),
  });
  const results = useQuery({
    queryKey: ["self-search", searched],
    queryFn: () =>
      apiFetch<Claimable[]>(
        `/me/player/search?name=${encodeURIComponent(searched!.name)}&date_of_birth=${searched!.dob}`,
      ),
    enabled: !!searched,
  });
  const send = useMutation({
    mutationFn: (c: Claimable) =>
      apiFetch<MyClaim>("/me/player/claims", {
        method: "POST",
        json: {
          player_id: c.player_id,
          date_of_birth: searched!.dob,
          message: note.trim() || null,
        },
      }),
    onSuccess: () => {
      setChosen(null);
      setNote("");
      qc.invalidateQueries({ queryKey: CLAIMS });
    },
  });
  const cancel = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/me/player/claims/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CLAIMS }),
  });

  const pending = claims.data?.find((c) => c.status === "pending");
  const lastNo = claims.data?.find((c) => c.status === "rejected");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Your player account"
        title="Find your profile"
        meta="Clubs on ScoutSphere keep a record of you. Link it to this account to see and update it yourself."
      />

      {pending ? (
        <Card className="space-y-3 border-l-4 border-l-volt">
          <p className="eyebrow text-link">Waiting for confirmation</p>
          <h2>{pending.player_name}</h2>
          <p className="text-sm opacity-75">
            {pending.reviewed_by} will check that this is you. You&apos;ll get a
            notification as soon as they decide. Sent{" "}
            {timeAgo(pending.created_at)}.
          </p>
          {pending.message && (
            <p className="rounded-[2px] bg-surface-2 p-3 text-sm">
              Your note: {pending.message}
            </p>
          )}
          <ErrorText>{cancel.error && msg(cancel.error)}</ErrorText>
          <Button
            variant="secondary"
            onClick={() => cancel.mutate(pending.id)}
            disabled={cancel.isPending}
          >
            Cancel request
          </Button>
        </Card>
      ) : (
        <>
          {lastNo && (
            <Card className="border-l-4 border-l-bad">
              <p className="eyebrow text-bad">Request declined</p>
              <p className="mt-1 text-sm">
                {lastNo.reviewed_by} didn&apos;t confirm{" "}
                <strong>{lastNo.player_name}</strong>
                {lastNo.decision_note ? `: ${lastNo.decision_note}` : "."} You
                can search again below.
              </p>
            </Card>
          )}
          <Card className="space-y-4">
            <h2>Who are you?</h2>
            <p className="text-sm opacity-70">
              Enter your name exactly as your club would have it, and your date
              of birth. Both must match, so nobody else can find your profile.
            </p>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (name.trim().length >= 2 && dob)
                  setSearched({ name: name.trim(), dob });
                setChosen(null);
              }}
            >
              <label className="flex min-w-48 flex-1 flex-col gap-1">
                <span className="eyebrow opacity-70">Full name</span>
                <input
                  className={fieldClass}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="eyebrow opacity-70">Date of birth</span>
                <input
                  type="date"
                  className={fieldClass}
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  autoComplete="bday"
                />
              </label>
              <Button type="submit" disabled={name.trim().length < 2 || !dob}>
                Search
              </Button>
            </form>
          </Card>

          {results.isFetching && (
            <p aria-busy="true" className="text-sm opacity-70">
              Searching…
            </p>
          )}
          {results.data && results.data.length === 0 && (
            <Card>
              <p className="text-sm">
                We couldn&apos;t find a profile with that name and date of
                birth. Check the spelling, or ask your club to add you first.
              </p>
            </Card>
          )}
          {results.data?.map((c) => (
            <Card key={c.player_id} className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <PlayerAvatar name={c.full_name} src={null} size="md" />
                  <div>
                    <p className="font-semibold">{c.full_name}</p>
                    <p className="text-sm opacity-70">
                      {[
                        `${c.age} years`,
                        c.nationality,
                        c.current_club?.club_name,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  <PositionChip code={c.primary_position} />
                </div>
                {chosen !== c.player_id && (
                  <Button onClick={() => setChosen(c.player_id)}>
                    This is me
                  </Button>
                )}
              </div>
              {chosen === c.player_id && (
                <div className="space-y-3 border-t border-line pt-3">
                  <label className="flex flex-col gap-1">
                    <span className="eyebrow opacity-70">
                      Note for {c.reviewed_by} (optional)
                    </span>
                    <textarea
                      rows={2}
                      maxLength={500}
                      className={`${fieldClass} h-auto py-2`}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="For example: I play for the U21 squad."
                    />
                  </label>
                  <ErrorText>{send.error && msg(send.error)}</ErrorText>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => send.mutate(c)}
                      disabled={send.isPending}
                    >
                      {send.isPending ? "Sending…" : "Send request"}
                    </Button>
                    <Button variant="secondary" onClick={() => setChosen(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </>
      )}
    </div>
  );
}

// ---- linked: your own profile ------------------------------------------------------------
function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="space-y-4">
      <div>
        <h2>{title}</h2>
        {hint && <p className="mt-1 text-sm opacity-65">{hint}</p>}
      </div>
      {children}
    </Card>
  );
}

function AboutForm({ p }: { p: SelfProfile }) {
  const qc = useQueryClient();
  const [v, setV] = useState({
    nationality: p.nationality ?? "",
    height_cm: p.height_cm ? String(p.height_cm) : "",
    weight_kg: p.weight_kg ? String(p.weight_kg) : "",
    preferred_foot: p.preferred_foot ?? "",
    primary_position: p.primary_position ?? "",
    secondary_positions: p.secondary_positions,
    biography: p.biography ?? "",
  });
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      apiFetch<SelfProfile>("/me/player", {
        method: "PATCH",
        json: {
          nationality: v.nationality.trim() || null,
          height_cm: v.height_cm ? Number(v.height_cm) : null,
          weight_kg: v.weight_kg ? Number(v.weight_kg) : null,
          preferred_foot: v.preferred_foot || null,
          primary_position: v.primary_position || null,
          secondary_positions: v.secondary_positions.filter(
            (s) => s !== v.primary_position,
          ),
          biography: v.biography.trim() || null,
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(KEY, data);
      setSaved(true);
    },
  });
  const set =
    (k: keyof typeof v) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setSaved(false);
      setV((s) => ({ ...s, [k]: e.target.value }));
    };

  return (
    <Section
      title="About you"
      hint="Your club keeps your name, date of birth, contract and medical details. These are yours to keep up to date."
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="eyebrow opacity-70">Nationality</span>
          <input
            className={fieldClass}
            value={v.nationality}
            onChange={set("nationality")}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow opacity-70">Preferred foot</span>
          <select
            className={`${fieldClass} capitalize`}
            value={v.preferred_foot}
            onChange={set("preferred_foot")}
          >
            <option value="">Not set</option>
            {FEET.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow opacity-70">Height (cm)</span>
          <input
            inputMode="numeric"
            className={fieldClass}
            value={v.height_cm}
            onChange={set("height_cm")}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow opacity-70">Weight (kg)</span>
          <input
            inputMode="numeric"
            className={fieldClass}
            value={v.weight_kg}
            onChange={set("weight_kg")}
          />
        </label>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="eyebrow opacity-70">Main position</span>
          <select
            className={fieldClass}
            value={v.primary_position}
            onChange={set("primary_position")}
          >
            <option value="">Not set</option>
            {POSITIONS.map((pos) => (
              <option key={pos}>{pos}</option>
            ))}
          </select>
        </label>
        <fieldset className="sm:col-span-2">
          <legend className="eyebrow mb-1.5 opacity-70">
            Other positions you can play (up to 4)
          </legend>
          <div className="flex flex-wrap gap-1.5">
            {POSITIONS.filter((pos) => pos !== v.primary_position).map(
              (pos) => {
                const on = v.secondary_positions.includes(pos);
                return (
                  <button
                    type="button"
                    key={pos}
                    aria-pressed={on}
                    disabled={!on && v.secondary_positions.length >= 4}
                    onClick={() => {
                      setSaved(false);
                      setV((s) => ({
                        ...s,
                        secondary_positions: on
                          ? s.secondary_positions.filter((x) => x !== pos)
                          : [...s.secondary_positions, pos],
                      }));
                    }}
                    className={`chip h-7 border px-2.5! transition-colors disabled:opacity-40 ${
                      on
                        ? "border-ink bg-accent text-accent-ink"
                        : "border-line-strong hover:border-ink"
                    }`}
                  >
                    {pos}
                  </button>
                );
              },
            )}
          </div>
        </fieldset>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="eyebrow opacity-70">About me</span>
          <textarea
            rows={5}
            maxLength={5000}
            className={`${fieldClass} h-auto py-2`}
            value={v.biography}
            onChange={(e) => {
              setSaved(false);
              setV((s) => ({ ...s, biography: e.target.value }));
            }}
            placeholder="Your style of play, strengths, what you're working on…"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
          {saved && (
            <span role="status" className="text-sm text-ok">
              Saved. Your club sees these updates.
            </span>
          )}
          <ErrorText>{save.error && msg(save.error)}</ErrorText>
        </div>
      </form>
    </Section>
  );
}

function Privacy({ p }: { p: SelfProfile }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState(p.contact_email ?? "");
  const patch = useMutation({
    mutationFn: (json: Record<string, unknown>) =>
      apiFetch<SelfProfile>("/me/player", { method: "PATCH", json }),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
  const locked = p.is_minor;
  const options = [
    {
      value: "private",
      title: "Only my club",
      body: `Only ${p.managed_by ?? "the club that manages your profile"} and any club you currently play for can see you.`,
    },
    {
      value: "network",
      title: "Clubs on ScoutSphere",
      body: "Any organization using ScoutSphere can find your profile and shortlist you. Your photo and details are shown; your medical and contract data never are.",
    },
  ];

  return (
    <Section
      title="Who can find you"
      hint="You decide. You can change this at any time."
    >
      {locked && (
        <p className="rounded-[2px] border-l-4 border-warn bg-warn-soft p-3 text-sm">
          You&apos;re under 18, so these settings stay with your club for now.
          They&apos;ll check with your parent or guardian before changing them.
        </p>
      )}
      <fieldset className="space-y-2" disabled={locked || patch.isPending}>
        <legend className="sr-only">Profile visibility</legend>
        {options.map((o) => (
          <label
            key={o.value}
            className={`flex cursor-pointer gap-3 rounded-[3px] border p-3 transition-colors ${
              p.visibility === o.value
                ? "border-ink bg-volt/10"
                : "border-line hover:border-line-strong"
            } ${locked ? "cursor-not-allowed opacity-70" : ""}`}
          >
            <input
              type="radio"
              name="visibility"
              className="mt-1"
              checked={p.visibility === o.value}
              onChange={() => patch.mutate({ visibility: o.value })}
            />
            <span>
              <span className="block text-sm font-semibold">{o.title}</span>
              <span className="block text-sm opacity-70">{o.body}</span>
            </span>
          </label>
        ))}
      </fieldset>

      {!locked && (
        <div className="space-y-3 border-t border-line pt-4">
          <label className="flex cursor-pointer items-center justify-between gap-4">
            <span>
              <span className="block text-sm font-semibold">
                Open to offers
              </span>
              <span className="block text-sm opacity-70">
                Other clubs that can see you also get your contact email, so
                they can reach you.
              </span>
            </span>
            <input
              type="checkbox"
              role="switch"
              className="switch"
              checked={p.open_to_offers}
              disabled={patch.isPending}
              onChange={(e) => {
                const json: Record<string, unknown> = {
                  open_to_offers: e.target.checked,
                };
                if (e.target.checked && email.trim())
                  json.contact_email = email.trim();
                patch.mutate(json);
              }}
            />
          </label>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              patch.mutate({ contact_email: email.trim() || null });
            }}
          >
            <label className="flex min-w-60 flex-1 flex-col gap-1">
              <span className="eyebrow opacity-70">Contact email</span>
              <input
                type="email"
                className={fieldClass}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <Button
              type="submit"
              variant="secondary"
              disabled={patch.isPending || email === (p.contact_email ?? "")}
            >
              Save email
            </Button>
          </form>
        </div>
      )}
      <ErrorText>{patch.error && msg(patch.error)}</ErrorText>
    </Section>
  );
}

function Profile({ p }: { p: SelfProfile }) {
  const qc = useQueryClient();
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-5 border-b border-line pb-6">
        <PlayerAvatar name={p.full_name} src={p.photo_url} size="xl" />
        <div className="min-w-0 space-y-2">
          <p className="eyebrow text-link">Your profile</p>
          <h1>{p.full_name}</h1>
          <p className="flex flex-wrap items-center gap-2 text-sm opacity-80">
            {p.age} years
            {p.nationality && <span>· {p.nationality}</span>}
            {p.current_club && <span>· {p.current_club.club_name}</span>}
            <PositionChip code={p.primary_position} />
          </p>
          <p className="text-xs opacity-60">
            Linked to the record kept by {p.managed_by ?? "your club"}.
          </p>
        </div>
      </header>

      <Section
        title="Photo"
        hint="Clubs see this on your profile. Location and camera details are removed from every upload."
      >
        <PhotoEditor
          name={p.full_name}
          current={p.photo_url}
          onSave={async (file, crop) => {
            const body = new FormData();
            body.append("file", file);
            body.append("crop_x", String(crop.x));
            body.append("crop_y", String(crop.y));
            body.append("crop_size", String(crop.size));
            qc.setQueryData(
              KEY,
              await apiFetch<SelfProfile>("/me/player/photo", {
                method: "PUT",
                body,
              }),
            );
          }}
          onRemove={async () => {
            qc.setQueryData(
              KEY,
              await apiFetch<SelfProfile>("/me/player/photo", {
                method: "DELETE",
              }),
            );
          }}
        />
      </Section>

      <AboutForm key={`${p.height_cm}-${p.biography}`} p={p} />
      <Privacy p={p} />

      <section className="space-y-3" aria-labelledby="career-title">
        <div>
          <h2 id="career-title">Your career</h2>
          <p className="mt-1 text-sm opacity-65">
            Recorded by the clubs you&apos;ve played for. To correct something,
            ask your club.
          </p>
        </div>
        <TableCard>
          <table className="data-table">
            <thead>
              <tr>
                <th>Club</th>
                <th>Period</th>
                <th className="num">Apps</th>
                <th className="num">Goals</th>
                <th className="num">Assists</th>
              </tr>
            </thead>
            <tbody>
              {p.career.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8! text-center opacity-70">
                    Nothing recorded yet.
                  </td>
                </tr>
              )}
              {p.career.map((s, i) => (
                <tr key={i}>
                  <td>
                    <span className="font-semibold">{s.club_name}</span>
                    <span className="sub">
                      {[s.team_label, label(s.spell_type)]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </td>
                  <td className="whitespace-nowrap">
                    {shortDate(s.start_date)} –{" "}
                    {s.end_date ? shortDate(s.end_date) : "now"}
                  </td>
                  <td className="num">{s.appearances ?? "—"}</td>
                  <td className="num">{s.goals ?? "—"}</td>
                  <td className="num">{s.assists ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableCard>
      </section>
    </div>
  );
}

export default function PlayerPortal() {
  const { user } = useAuth();
  const profile = useQuery({
    queryKey: KEY,
    queryFn: () => apiFetch<SelfProfile>("/me/player"),
    retry: (n, e) =>
      !(e instanceof ApiError && e.code === "no_profile") && n < 2,
    enabled: user?.account_type === "player",
  });

  if (user && user.account_type !== "player")
    return (
      <Card>
        <p className="text-sm">This page is for player accounts.</p>
      </Card>
    );
  if (profile.isLoading)
    return (
      <p aria-busy="true" className="text-sm opacity-70">
        Loading…
      </p>
    );
  if (profile.data) return <Profile p={profile.data} />;
  if (profile.error instanceof ApiError && profile.error.code === "no_profile")
    return <ClaimFlow />;
  return <ErrorText>{profile.error && msg(profile.error)}</ErrorText>;
}
