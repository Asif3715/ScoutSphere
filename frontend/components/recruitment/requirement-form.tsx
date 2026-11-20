"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { ApiError } from "@/lib/http";
import {
  requirementPayload,
  requirementSchema,
  type RequirementValues,
} from "@/lib/schemas";
import {
  FEET,
  POSITIONS,
  PRIORITIES,
  RATING_GROUPS,
  label,
  type Requirement,
} from "@/lib/types";

const select =
  "w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm";

export function toRequirementValues(r?: Requirement): RequirementValues {
  const attributes: Record<string, string> = {};
  for (const attrs of Object.values(RATING_GROUPS))
    for (const a of attrs)
      attributes[a] = r?.attributes[a] ? String(r.attributes[a]) : "";
  const s = (n: number | null | undefined) => (n != null ? String(n) : "");
  return {
    title: r?.title ?? "",
    position: r?.position ?? "",
    min_age: s(r?.min_age),
    max_age: s(r?.max_age),
    nationality: r?.nationality ?? "",
    preferred_foot:
      (r?.preferred_foot as RequirementValues["preferred_foot"]) ?? "",
    min_appearances: s(r?.min_appearances),
    budget_min: s(r?.budget_min),
    budget_max: s(r?.budget_max),
    currency: r?.currency ?? "",
    contract_notes: r?.contract_notes ?? "",
    instructions: r?.instructions ?? "",
    priority: (r?.priority as RequirementValues["priority"]) ?? "medium",
    attributes,
  };
}

export function RequirementForm({
  requirement,
  submitLabel,
  onSubmit,
}: {
  requirement?: Requirement;
  submitLabel: string;
  onSubmit: (payload: ReturnType<typeof requirementPayload>) => Promise<void>;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RequirementValues>({
    resolver: zodResolver(requirementSchema),
    defaultValues: toRequirementValues(requirement),
  });

  const submit = handleSubmit(async (v) => {
    setFormError(null);
    try {
      await onSubmit(requirementPayload(v));
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
      className="max-w-3xl space-y-6"
      noValidate
    >
      <Card className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <Field
            label="Title"
            error={errors.title?.message}
            {...register("title")}
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="position" className="block text-sm font-medium">
            Position
          </label>
          <select id="position" className={select} {...register("position")}>
            <option value="">Choose…</option>
            {POSITIONS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <ErrorText>{errors.position?.message}</ErrorText>
        </div>
        <div className="space-y-1">
          <label htmlFor="priority" className="block text-sm font-medium">
            Priority
          </label>
          <select id="priority" className={select} {...register("priority")}>
            {PRIORITIES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>
        <Field
          label="Minimum age"
          inputMode="numeric"
          error={errors.min_age?.message}
          {...register("min_age")}
        />
        <Field
          label="Maximum age"
          inputMode="numeric"
          error={errors.max_age?.message}
          {...register("max_age")}
        />
        <Field
          label="Preferred nationality"
          error={errors.nationality?.message}
          {...register("nationality")}
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
            <option value="">Any</option>
            {FEET.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
        </div>
        <Field
          label="Minimum career appearances"
          inputMode="numeric"
          error={errors.min_appearances?.message}
          {...register("min_appearances")}
        />
      </Card>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Required attributes</h2>
        <p className="text-xs opacity-60">
          Minimum <em>average</em> scout rating (1–10) across your approved
          reports. Leave blank for no requirement.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(RATING_GROUPS).map(([group, attrs]) => (
            <Card key={group} className="space-y-2">
              <h3 className="text-sm font-semibold capitalize">{group}</h3>
              {attrs.map((a) => (
                <div
                  key={a}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <label htmlFor={`attr-${a}`} className="capitalize">
                    {label(a)}
                  </label>
                  <input
                    id={`attr-${a}`}
                    inputMode="numeric"
                    maxLength={2}
                    className="w-14 rounded-[2px] border border-line-strong bg-transparent px-2 py-1 text-center text-sm"
                    {...register(`attributes.${a}`)}
                  />
                </div>
              ))}
            </Card>
          ))}
        </div>
        {errors.attributes && (
          <ErrorText>
            Attribute minimums must be whole numbers from 1 to 10.
          </ErrorText>
        )}
      </section>

      <Card className="grid grid-cols-3 gap-4">
        <Field
          label="Budget from"
          inputMode="numeric"
          error={errors.budget_min?.message}
          {...register("budget_min")}
        />
        <Field
          label="Budget to"
          inputMode="numeric"
          error={errors.budget_max?.message}
          {...register("budget_max")}
        />
        <Field
          label="Currency"
          placeholder="EUR"
          error={errors.currency?.message}
          {...register("currency")}
        />
        <p className="col-span-3 text-xs opacity-60">
          The budget is recorded for your team. Fees and market values are not
          tracked yet, so it is not used for matching.
        </p>
      </Card>

      <section className="space-y-3">
        {(
          [
            ["contract_notes", "Contract requirements"],
            ["instructions", "Additional instructions"],
          ] as const
        ).map(([name, text]) => (
          <div key={name} className="space-y-1">
            <label htmlFor={name} className="block text-sm font-medium">
              {text}
            </label>
            <textarea
              id={name}
              rows={3}
              className={select}
              {...register(name)}
            />
          </div>
        ))}
      </section>

      <ErrorText>{formError}</ErrorText>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
