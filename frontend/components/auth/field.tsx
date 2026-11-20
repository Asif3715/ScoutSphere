import Link from "next/link";
import type { ComponentProps } from "react";

import { LogoMark, PitchArt, Wordmark } from "@/components/brand/brand";

type Props = ComponentProps<"input"> & { label: string; error?: string };

export function Field({ label, error, id, ...input }: Props) {
  const fieldId = id ?? input.name;
  return (
    <div className="space-y-1.5">
      <label htmlFor={fieldId} className="eyebrow block opacity-80">
        {label}
      </label>
      <input
        id={fieldId}
        aria-invalid={!!error}
        aria-describedby={error ? `${fieldId}-error` : undefined}
        className="w-full rounded-[2px] border border-line-strong bg-surface px-3 py-2.5 text-[0.95rem] transition-shadow outline-none aria-[invalid=true]:border-bad"
        {...input}
      />
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
          <div>{children}</div>
        </div>
      </main>
    </div>
  );
}
