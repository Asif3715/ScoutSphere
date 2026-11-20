"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { ApiError } from "@/lib/http";
import { playerPayload, playerSchema, type PlayerValues } from "@/lib/schemas";
import {
  FEET,
  POSITIONS,
  VISIBILITIES,
  VISIBILITY_LABELS,
  type DuplicateCandidate,
  type Player,
} from "@/lib/types";

export function toPlayerValues(p?: Player): PlayerValues {
  return {
    full_name: p?.full_name ?? "",
    date_of_birth: p?.date_of_birth ?? "",
    nationality: p?.nationality ?? "",
    height_cm: p?.height_cm ? String(p.height_cm) : "",
    weight_kg: p?.weight_kg ? String(p.weight_kg) : "",
    preferred_foot: (p?.preferred_foot as PlayerValues["preferred_foot"]) ?? "",
    primary_position: p?.primary_position ?? "",
    secondary_positions: p?.secondary_positions ?? [],
    visibility: (p?.visibility as PlayerValues["visibility"]) ?? "private",
    profile_picture_url: p?.profile_picture_url ?? "",
    biography: p?.biography ?? "",
  };
}

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

export function PlayerForm({
  player,
  submitLabel,
  onSubmit,
}: {
  player?: Player;
  submitLabel: string;
  onSubmit: (
    payload: ReturnType<typeof playerPayload>,
    allowDuplicate: boolean,
  ) => Promise<void>;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicates, setDuplicates] = useState<DuplicateCandidate[] | null>(
    null,
  );
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<PlayerValues>({
    resolver: zodResolver(playerSchema),
    defaultValues: toPlayerValues(player),
  });

  async function send(values: PlayerValues, allowDuplicate: boolean) {
    setFormError(null);
    try {
      await onSubmit(playerPayload(values), allowDuplicate);
    } catch (e) {
      if (e instanceof ApiError && e.code === "possible_duplicate") {
        setDuplicates((e.details as unknown as DuplicateCandidate[]) ?? []);
      } else {
        setFormError(
          e instanceof ApiError ? e.message : "Could not reach the server",
        );
      }
    }
  }
  const submit = handleSubmit((v) => send(v, false));

  return (
    <form
      method="post"
      onSubmit={submit}
      className="max-w-2xl space-y-4"
      noValidate
    >
      {duplicates && (
        <Card className="space-y-2 border-warn bg-warn-soft text-warn">
          <p className="font-semibold">
            This might be a player who already exists
          </p>
          <ul className="list-disc pl-5 text-sm">
            {duplicates.map((d) => (
              <li key={d.id}>
                <a
                  className="underline"
                  href={`/players/${d.id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {d.full_name}
                </a>{" "}
                — born {d.date_of_birth}
                {d.nationality ? `, ${d.nationality}` : ""} (
                {Math.round(d.similarity * 100)}% name match)
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={isSubmitting}
              onClick={() => send(getValues(), true)}
            >
              This is a different person — create anyway
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setDuplicates(null)}
            >
              Cancel
            </Button>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <Field
            label="Full name"
            error={errors.full_name?.message}
            {...register("full_name")}
          />
        </div>
        <Field
          label="Date of birth"
          type="date"
          error={errors.date_of_birth?.message}
          {...register("date_of_birth")}
        />
        <Field
          label="Nationality"
          error={errors.nationality?.message}
          {...register("nationality")}
        />
        <Field
          label="Height (cm)"
          inputMode="numeric"
          error={errors.height_cm?.message}
          {...register("height_cm")}
        />
        <Field
          label="Weight (kg)"
          inputMode="numeric"
          error={errors.weight_kg?.message}
          {...register("weight_kg")}
        />

        <div className="space-y-1">
          <label htmlFor="preferred_foot" className="block text-sm font-medium">
            Preferred foot
          </label>
          <select
            id="preferred_foot"
            className={select}
            {...register("preferred_foot")}
          >
            <option value="">—</option>
            {FEET.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label
            htmlFor="primary_position"
            className="block text-sm font-medium"
          >
            Primary position
          </label>
          <select
            id="primary_position"
            className={select}
            {...register("primary_position")}
          >
            <option value="">—</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
      </div>

      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">
          Secondary positions (max 4)
        </legend>
        <div className="flex flex-wrap gap-3 text-sm">
          {POSITIONS.map((p) => (
            <label key={p} className="flex items-center gap-1">
              <input
                type="checkbox"
                value={p}
                {...register("secondary_positions")}
              />{" "}
              {p}
            </label>
          ))}
        </div>
        <ErrorText>
          {errors.secondary_positions?.message as string | undefined}
        </ErrorText>
      </fieldset>

      <div className="space-y-1">
        <label htmlFor="visibility" className="block text-sm font-medium">
          Who can see this player?
        </label>
        <select id="visibility" className={select} {...register("visibility")}>
          {VISIBILITIES.map((v) => (
            <option key={v} value={v}>
              {VISIBILITY_LABELS[v]}
            </option>
          ))}
        </select>
        <p className="text-xs opacity-60">
          Players under 18 can never have a public profile, and other
          organizations never see a minor&apos;s photo or biography.
        </p>
      </div>

      <Field
        label="Photo link (optional)"
        hint="Only if the photo is hosted elsewhere. Uploading a photo is preferred and replaces this."
        error={errors.profile_picture_url?.message}
        {...register("profile_picture_url")}
      />
      <div className="space-y-1">
        <label htmlFor="biography" className="block text-sm font-medium">
          Biography
        </label>
        <textarea
          id="biography"
          rows={4}
          className={select}
          {...register("biography")}
        />
        <ErrorText>{errors.biography?.message}</ErrorText>
      </div>

      <ErrorText>{formError}</ErrorText>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
