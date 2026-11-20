"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";

import { AuthCard, Field, PasswordField } from "@/components/auth/field";
import { ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { authErrorMessage, fieldErrors } from "@/lib/auth-errors";
import { setFlash } from "@/lib/flash";
import { ApiError } from "@/lib/http";
import { safeNext } from "@/lib/redirect";
import { registerSchema, type RegisterValues } from "@/lib/schemas";
import { useHydrated } from "@/lib/use-hydrated";

const FIELDS = ["full_name", "email", "password", "account_type"] as const;

function RegisterForm() {
  const { register: registerUser, login } = useAuth();
  const router = useRouter();
  const hydrated = useHydrated();
  const next = safeNext(useSearchParams().get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  const [emailTaken, setEmailTaken] = useState(false);
  const loginHref = `/login${next !== "/dashboard" ? `?next=${encodeURIComponent(next)}` : ""}`;
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    mode: "onTouched",
    defaultValues: { account_type: "standard" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    setEmailTaken(false);
    const firstName = values.full_name.trim().split(/\s+/)[0];
    const email = values.email.trim();

    // Step 1: create the account.
    try {
      await registerUser({ ...values, email });
    } catch (e) {
      setFormError(authErrorMessage(e, "register"));
      if (e instanceof ApiError && e.code === "email_taken") {
        setEmailTaken(true);
        setError("email", {
          message: "An account with this email already exists.",
        });
      }
      for (const [field, message] of Object.entries(fieldErrors(e))) {
        if ((FIELDS as readonly string[]).includes(field))
          setError(field as (typeof FIELDS)[number], { message });
      }
      return;
    }

    // Step 2: sign straight in. If that fails the account still exists, so say so plainly.
    try {
      await login(email, values.password);
      setFlash({
        kind: "success",
        text: `Account created. Welcome to ScoutSphere, ${firstName}!`,
      });
      router.replace(next);
    } catch {
      setFlash({
        kind: "success",
        text: "Your account was created. Please sign in to continue.",
      });
      router.replace(loginHref);
    }
  });

  return (
    <AuthCard title="Create your account">
      <form method="post" onSubmit={onSubmit} className="space-y-4" noValidate>
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
        <PasswordField
          label="Password"
          autoComplete="new-password"
          hint="At least 10 characters. A short phrase is easier to remember."
          error={errors.password?.message}
          {...register("password")}
        />
        <PasswordField
          label="Confirm password"
          autoComplete="new-password"
          error={errors.confirm?.message}
          {...register("confirm")}
        />
        <div className="space-y-1.5">
          <label htmlFor="account_type" className="eyebrow block opacity-80">
            I am a
          </label>
          <select
            id="account_type"
            {...register("account_type")}
            className="w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2.5 text-sm"
          >
            <option value="standard">Club staff / scout</option>
            <option value="player">Player</option>
            <option value="agent">Football agent</option>
          </select>
          <p className="text-xs opacity-60">
            Only club staff can create an organization. Players and agents join
            one by invitation.
          </p>
        </div>
        <ErrorText>{formError}</ErrorText>
        {emailTaken && (
          <p className="text-sm">
            <Link href={loginHref} className="text-link underline">
              Sign in with this email instead →
            </Link>
          </p>
        )}
        <button
          type="submit"
          disabled={!hydrated || isSubmitting}
          aria-busy={isSubmitting}
          className="btn btn-primary w-full py-3"
        >
          {!hydrated
            ? "Loading…"
            : isSubmitting
              ? "Creating account…"
              : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-sm">
        Already registered?{" "}
        <Link href={loginHref} className="text-link underline">
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
