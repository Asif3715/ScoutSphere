"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { AuthCard, Field } from "@/components/auth/field";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/http";
import { safeNext } from "@/lib/redirect";
import { loginSchema, type LoginValues } from "@/lib/schemas";

function LoginForm() {
  const { user, loading, login } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, router, next]);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login(values.email, values.password);
      router.replace(next);
    } catch (e) {
      setFormError(
        e instanceof ApiError ? e.message : "Could not reach the server",
      );
    }
  });

  return (
    <AuthCard title="Sign in to your account">
      <form method="post" onSubmit={onSubmit} className="space-y-4" noValidate>
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
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        {formError && (
          <p role="alert" className="text-sm text-bad">
            {formError}
          </p>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="btn btn-primary w-full py-3"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-4 text-sm">
        No account?{" "}
        <Link
          href={`/register${next !== "/dashboard" ? `?next=${encodeURIComponent(next)}` : ""}`}
          className="text-link underline"
        >
          Register
        </Link>
      </p>
    </AuthCard>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
