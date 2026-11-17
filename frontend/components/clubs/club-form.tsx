"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, ErrorText } from "@/components/ui/ui";
import { ApiError } from "@/lib/http";
import { clubPayload, clubSchema, type ClubValues } from "@/lib/schemas";
import type { Club } from "@/lib/types";

export function toFormValues(club?: Club): ClubValues {
  return {
    name: club?.name ?? "",
    short_name: club?.short_name ?? "",
    country: club?.country ?? "",
    city: club?.city ?? "",
    founded_year: club?.founded_year ? String(club.founded_year) : "",
    website: club?.website ?? "",
    contact_email: club?.contact_email ?? "",
    contact_phone: club?.contact_phone ?? "",
    description: club?.description ?? "",
  };
}

export function ClubForm({
  club,
  submitLabel,
  onSubmit,
}: {
  club?: Club;
  submitLabel: string;
  onSubmit: (payload: ReturnType<typeof clubPayload>) => Promise<void>;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ClubValues>({
    resolver: zodResolver(clubSchema),
    defaultValues: toFormValues(club),
  });

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await onSubmit(clubPayload(values));
    } catch (e) {
      if (e instanceof ApiError && e.code === "club_exists")
        setError("name", { message: e.message });
      else
        setFormError(
          e instanceof ApiError ? e.message : "Could not reach the server",
        );
    }
  });

  return (
    <form onSubmit={submit} className="max-w-xl space-y-4" noValidate>
      <Field
        label="Club name"
        error={errors.name?.message}
        {...register("name")}
      />
      <div className="grid grid-cols-2 gap-4">
        <Field
          label="Short name"
          error={errors.short_name?.message}
          {...register("short_name")}
        />
        <Field
          label="Founded (year)"
          inputMode="numeric"
          error={errors.founded_year?.message}
          {...register("founded_year")}
        />
        <Field
          label="Country"
          error={errors.country?.message}
          {...register("country")}
        />
        <Field
          label="City"
          error={errors.city?.message}
          {...register("city")}
        />
        <Field
          label="Website"
          error={errors.website?.message}
          {...register("website")}
        />
        <Field
          label="Contact email"
          type="email"
          error={errors.contact_email?.message}
          {...register("contact_email")}
        />
        <Field
          label="Contact phone"
          error={errors.contact_phone?.message}
          {...register("contact_phone")}
        />
      </div>
      <div className="space-y-1">
        <label htmlFor="description" className="block text-sm font-medium">
          Description
        </label>
        <textarea
          id="description"
          rows={4}
          className="w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm"
          {...register("description")}
        />
        <ErrorText>{errors.description?.message}</ErrorText>
      </div>
      <ErrorText>{formError}</ErrorText>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
