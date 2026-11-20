"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, ErrorText } from "@/components/ui/ui";
import { ApiError } from "@/lib/http";
import { scoutPayload, scoutSchema, type ScoutValues } from "@/lib/schemas";
import { AGE_GROUPS, POSITIONS, type Member, type Scout } from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

export function toScoutValues(s?: Scout): ScoutValues {
  return {
    user_id: s?.user_id ?? "",
    bio: s?.bio ?? "",
    experience_years:
      s?.experience_years != null ? String(s.experience_years) : "",
    positions: s?.positions ?? [],
    age_groups: s?.age_groups ?? [],
    regions: s?.regions.join(", ") ?? "",
  };
}

export function ScoutForm({
  scout,
  members,
  submitLabel,
  onSubmit,
}: {
  scout?: Scout;
  /** When provided (create mode for managers), lets you pick which member to profile. */
  members?: Member[];
  submitLabel: string;
  onSubmit: (
    payload: ReturnType<typeof scoutPayload> & { user_id?: string },
  ) => Promise<void>;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ScoutValues>({
    resolver: zodResolver(scoutSchema),
    defaultValues: toScoutValues(scout),
  });

  const submit = handleSubmit(async (v) => {
    setFormError(null);
    try {
      const payload = scoutPayload(v);
      await onSubmit(v.user_id ? { ...payload, user_id: v.user_id } : payload);
    } catch (e) {
      setFormError(
        e instanceof ApiError ? e.message : "Could not reach the server",
      );
    }
  });

  return (
    <form
      method="post"
      onSubmit={submit}
      className="max-w-xl space-y-4"
      noValidate
    >
      {members && (
        <div className="space-y-1">
          <label htmlFor="user_id" className="block text-sm font-medium">
            Member
          </label>
          <select id="user_id" className={select} {...register("user_id")}>
            <option value="">Myself</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name} ({m.email})
              </option>
            ))}
          </select>
        </div>
      )}
      <Field
        label="Years of experience"
        inputMode="numeric"
        error={errors.experience_years?.message}
        {...register("experience_years")}
      />
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">Positions covered</legend>
        <div className="flex flex-wrap gap-3 text-sm">
          {POSITIONS.map((p) => (
            <label key={p} className="flex items-center gap-1">
              <input type="checkbox" value={p} {...register("positions")} /> {p}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">Age groups</legend>
        <div className="flex flex-wrap gap-3 text-sm">
          {AGE_GROUPS.map((g) => (
            <label key={g} className="flex items-center gap-1">
              <input type="checkbox" value={g} {...register("age_groups")} />{" "}
              {g}
            </label>
          ))}
        </div>
      </fieldset>
      <Field
        label="Regions or countries (comma separated)"
        error={errors.regions?.message}
        {...register("regions")}
      />
      <div className="space-y-1">
        <label htmlFor="bio" className="block text-sm font-medium">
          Bio
        </label>
        <textarea id="bio" rows={4} className={select} {...register("bio")} />
        <ErrorText>{errors.bio?.message}</ErrorText>
      </div>
      <ErrorText>{formError}</ErrorText>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
