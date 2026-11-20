"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { organizationSchema, type OrganizationValues } from "@/lib/schemas";
import type { Organization } from "@/lib/types";

export default function OnboardingPage() {
  const { user, refreshProfile } = useAuth();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<OrganizationValues>({
    resolver: zodResolver(organizationSchema),
  });

  const canCreate = user?.account_type === "standard";

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const org = await apiFetch<Organization>("/organizations", {
        method: "POST",
        json: { name: values.name, description: values.description || null },
      });
      await refreshProfile(org.id);
      router.replace("/dashboard");
    } catch (e) {
      setFormError(
        e instanceof ApiError ? e.message : "Could not reach the server",
      );
    }
  });

  return (
    <div className="mx-auto max-w-md space-y-4 pt-10">
      <h1 className="text-2xl font-bold">Set up your organization</h1>
      <p className="text-sm opacity-70">
        An organization is your club&apos;s private workspace. You will become
        its owner and can invite your team afterwards.
      </p>
      {canCreate ? (
        <form method="post" onSubmit={submit} className="space-y-4" noValidate>
          <Field
            label="Organization name"
            error={errors.name?.message}
            {...register("name")}
          />
          <div className="space-y-1">
            <label htmlFor="description" className="block text-sm font-medium">
              Description (optional)
            </label>
            <textarea
              id="description"
              rows={3}
              className="w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm"
              {...register("description")}
            />
          </div>
          <ErrorText>{formError}</ErrorText>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating…" : "Create organization"}
          </Button>
        </form>
      ) : (
        <Card>
          <p className="text-sm">
            Player and agent accounts join organizations by invitation. Ask a
            club to invite you, then open the invitation link.
          </p>
        </Card>
      )}
    </div>
  );
}
