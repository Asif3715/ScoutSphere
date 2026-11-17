"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";

import { AuthCard, Field } from "@/components/auth/field";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/http";
import { safeNext } from "@/lib/redirect";
import { registerSchema, type RegisterValues } from "@/lib/schemas";

function RegisterForm() {
  const { register: registerUser } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { account_type: "standard" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await registerUser(values);
      router.replace(next);
    } catch (e) {
      if (e instanceof ApiError && e.code === "email_taken") {
        setError("email", { message: e.message });
      } else {
        setFormError(
          e instanceof ApiError ? e.message : "Could not reach the server",
        );
      }
    }
  });

  return (
    <AuthCard title="Create your account">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field
          label="Full name"
          autoComplete="name"
          error={errors.full_name?.message}
          {...register("full_name")}
        />
        <Field
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <Field
          label="Password"
          type="password"
          autoComplete="new-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <Field
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm?.message}
          {...register("confirm")}
        />
        <div className="space-y-1">
          <label htmlFor="account_type" className="block text-sm font-medium">
            I am a
          </label>
          <select
            id="account_type"
            {...register("account_type")}
            className="w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm"
          >
            <option value="standard">Club staff / scout</option>
            <option value="player">Player</option>
            <option value="agent">Football agent</option>
          </select>
        </div>
        {formError && (
          <p role="alert" className="text-sm text-red-600">
            {formError}
          </p>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-md bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-60"
        >
          {isSubmitting ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-sm">
        Already registered?{" "}
        <Link
          href={`/login${next !== "/dashboard" ? `?next=${encodeURIComponent(next)}` : ""}`}
          className="text-teal-600 underline"
        >
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}
