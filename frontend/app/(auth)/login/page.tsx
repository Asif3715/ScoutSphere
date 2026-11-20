"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { AuthCard, Field, PasswordField } from "@/components/auth/field";
import { ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { authErrorMessage, fieldErrors } from "@/lib/auth-errors";
import { ApiError } from "@/lib/http";
import { safeNext } from "@/lib/redirect";
import { loginSchema, type LoginValues } from "@/lib/schemas";
import { useHydrated } from "@/lib/use-hydrated";

function LoginForm() {
  const { user, loading, login } = useAuth();
  const router = useRouter();
  const hydrated = useHydrated();
  const next = safeNext(useSearchParams().get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  const [failures, setFailures] = useState(0);
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
  });

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, router, next]);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login(values.email.trim(), values.password);
      router.replace(next);
    } catch (e) {
      setFormError(authErrorMessage(e, "sign-in"));
      for (const [field, message] of Object.entries(fieldErrors(e))) {
        if (field === "email" || field === "password")
          setError(field, { message });
      }
      if (e instanceof ApiError && e.code === "invalid_credentials") {
        setFailures((n) => n + 1);
        // Keep the email, clear the password and put the cursor back there for a retry.
        setValue("password", "");
        setError("password", { message: "Incorrect email or password." });
        setFocus("password");
      }
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
        <PasswordField
          label="Password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <ErrorText>{formError}</ErrorText>
        {failures >= 3 && (
          <p className="text-xs opacity-70">
            Still having trouble? Password reset isn&apos;t available yet. If
            you&apos;re sure of the email, ask an organization admin for help,
            or register again with a different email.
          </p>
        )}
        <button
          type="submit"
          disabled={!hydrated || isSubmitting}
          aria-busy={isSubmitting}
          className="btn btn-primary w-full py-3"
        >
          {!hydrated ? "Loading…" : isSubmitting ? "Signing in…" : "Sign in"}
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
