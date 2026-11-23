"use client";

import Link from "next/link";
import { useState, type ComponentProps } from "react";

import { LogoMark, Wordmark } from "@/components/brand/brand";
import { PitchArt } from "@/components/brand/pitch-art";
import { FlashBanner } from "@/components/ui/flash-banner";

type Props = ComponentProps<"input"> & {
  label: string;
  error?: string;
  hint?: string;
};

export function Field({ label, error, hint, id, ...input }: Props) {
  const fieldId = id ?? input.name;
  return (
    <div className="space-y-1.5">
      <label htmlFor={fieldId} className="eyebrow block opacity-80">
        {label}
      </label>
      <input
        id={fieldId}
        aria-invalid={!!error}
        aria-describedby={
          error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined
        }
        className="w-full rounded-[2px] border border-line-strong bg-surface px-3 py-2.5 text-[0.95rem] transition-shadow outline-none aria-[invalid=true]:border-bad"
        {...input}
      />
      {hint && !error && (
        <p id={`${fieldId}-hint`} className="text-xs opacity-60">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fieldId}-error`} role="alert" className="text-xs text-bad">
          {error}
        </p>
      )}
    </div>
  );
}

/** Password input with a show/hide toggle and a Caps Lock warning. */
export function PasswordField({ label, error, hint, id, ...input }: Props) {
  const fieldId = id ?? input.name;
  const [visible, setVisible] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const describedBy = error
    ? `${fieldId}-error`
    : hint
      ? `${fieldId}-hint`
      : undefined;
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) =>
    setCapsLock(e.getModifierState?.("CapsLock") ?? false);
  return (
    <div className="space-y-1.5">
      <label htmlFor={fieldId} className="eyebrow block opacity-80">
        {label}
      </label>
      <div className="relative">
        <input
          id={fieldId}
          type={visible ? "text" : "password"}
          aria-invalid={!!error}
          aria-describedby={describedBy}
          onKeyDown={onKey}
          onKeyUp={onKey}
          className="w-full rounded-[2px] border border-line-strong bg-surface py-2.5 pr-16 pl-3 text-[0.95rem] transition-shadow outline-none aria-[invalid=true]:border-bad"
          {...input}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          aria-controls={fieldId}
          className="eyebrow absolute inset-y-0 right-0 px-3 opacity-60 hover:opacity-100"
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
      {capsLock && <p className="text-xs text-warn">Caps Lock is on.</p>}
      {hint && !error && (
        <p id={`${fieldId}-hint`} className="text-xs opacity-60">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fieldId}-error`} role="alert" className="text-xs text-bad">
          {error}
        </p>
      )}
    </div>
  );
}

const QUOTES = [
  ["Eyes on every pitch.", "Reports, ratings and recruitment in one dossier."],
  [
    "Find the player before the market does.",
    "Strict matching, no black-box scores.",
  ],
];

/** Split-screen frame for sign-in, registration and invitations. */
export function AuthCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [headline, sub] = QUOTES[title.length % QUOTES.length];
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-dugout p-12 text-dugout-ink lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden="true"
          className="absolute inset-0 [background:radial-gradient(700px_400px_at_20%_10%,rgb(198_244_50/0.14),transparent_60%)]"
        />
        <Link href="/" className="relative flex items-center gap-2.5">
          <LogoMark className="h-9 w-9" />
          <Wordmark />
        </Link>
        <PitchArt className="relative w-full max-w-xl self-center text-dugout-ink/40" />
        <div className="relative stagger">
          <p className="font-display text-5xl leading-[0.9] font-extrabold uppercase [font-variation-settings:'opsz'_72]">
            {headline}
          </p>
          <p className="eyebrow mt-4 text-volt/80">{sub}</p>
        </div>
      </section>
      <main className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="stagger mx-auto w-full max-w-sm">
          <Link href="/" className="mb-10 flex items-center gap-2 lg:hidden">
            <LogoMark className="h-8 w-8" />
            <Wordmark />
          </Link>
          <p className="eyebrow text-link">ScoutSphere · Access</p>
          <h1 className="mt-2 mb-8">{title}</h1>
          <FlashBanner className="mb-6" />
          <div>{children}</div>
        </div>
      </main>
    </div>
  );
}
