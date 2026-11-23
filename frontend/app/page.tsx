import Link from "next/link";
import { Suspense } from "react";

import { LogoMark, Wordmark } from "@/components/brand/brand";
import { PitchArt } from "@/components/brand/pitch-art";
import { fetchReadiness, type ReadinessResponse } from "@/lib/api";

async function BackendStatus() {
  let readiness: ReadinessResponse | null = null;
  try {
    readiness = await fetchReadiness();
  } catch {
    readiness = null;
  }
  const up = readiness?.status === "ok";
  return (
    <ul
      className="flex flex-wrap items-center gap-x-6 gap-y-2"
      data-testid="status-list"
    >
      <li className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className={`live-dot h-1.5 w-1.5 rounded-full ${up ? "bg-ok" : "bg-bad"}`}
        />
        Backend: {readiness ? readiness.status : "unreachable"}
      </li>
      {readiness &&
        Object.entries(readiness.checks).map(([name, state]) => (
          <li key={name}>
            {name}: {state}
          </li>
        ))}
    </ul>
  );
}

const FEATURES = [
  [
    "01",
    "Scout network",
    "Assign scouts to matches, competitions or individual players, with deadlines and reminders.",
  ],
  [
    "02",
    "Structured reports",
    "Twenty rated attributes, versioned submissions and a review trail nobody can rewrite.",
  ],
  [
    "03",
    "Recruitment pipeline",
    "Requirements that match players on every criterion, with each result explained.",
  ],
  [
    "04",
    "Side-by-side",
    "Compare up to five players. Recorded facts on one side, scout opinion on the other.",
  ],
];

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-6 md:px-10">
        <Link href="/" className="flex items-center gap-2.5">
          <LogoMark className="h-9 w-9" />
          <Wordmark />
        </Link>
        <nav className="flex items-center gap-3">
          <Link href="/login" className="btn btn-secondary">
            Sign in
          </Link>
          <Link
            href="/register"
            className="btn btn-primary hidden sm:inline-flex"
          >
            Start scouting
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-7xl px-6 md:px-10">
        <section className="grid items-center gap-10 pt-10 pb-16 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
          <div className="stagger">
            <p className="eyebrow text-link">
              Football talent intelligence · Season 26/27
            </p>
            <h1 className="mt-5 text-[clamp(3.4rem,2rem+6vw,7.5rem)]! leading-[0.9]!">
              Every player.
              <br />
              Every report.
              <br />
              <span className="marker">One dossier.</span>
            </h1>
            <p className="mt-8 max-w-lg text-lg leading-relaxed opacity-80">
              ScoutSphere brings clubs, scouts and recruitment staff onto the
              same pitch, from the first glimpse in a youth fixture to the
              signature on a contract.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Link
                href="/register"
                className="btn btn-primary px-5 py-3 text-[0.8rem]"
              >
                Create your club →
              </Link>
              <Link
                href="/login"
                className="btn btn-secondary px-5 py-3 text-[0.8rem]"
              >
                I have an account
              </Link>
            </div>
          </div>
          <div className="relative">
            <div className="relative rounded-[4px] bg-dugout p-5 text-dugout-ink shadow-[12px_12px_0_0_var(--volt)] ring-1 ring-white/10 md:p-8">
              <div className="mb-4 flex items-center justify-between">
                <span className="eyebrow text-volt">Live scouting map</span>
                <span className="eyebrow hidden items-center gap-2 opacity-60 sm:flex">
                  <span
                    aria-hidden="true"
                    className="live-dot h-1.5 w-1.5 rounded-full bg-volt"
                  />{" "}
                  5 targets tracked
                </span>
              </div>
              <PitchArt className="w-full text-dugout-ink/45" />
              <div className="mt-5 grid grid-cols-3 gap-3 border-t border-white/10 pt-4">
                {[
                  ["Passing", "8.4"],
                  ["Vision", "7.9"],
                  ["Work rate", "9.1"],
                ].map(([k, v]) => (
                  <div key={k}>
                    <p className="eyebrow opacity-50">{k}</p>
                    <p className="font-display text-4xl font-extrabold [font-variation-settings:'opsz'_72]">
                      {v}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="stagger grid gap-px overflow-hidden rounded-[3px] border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(([n, title, body]) => (
            <article
              key={n}
              className="group bg-surface p-6 transition-colors hover:bg-paper"
            >
              <p className="font-mono text-xs text-link">{n}</p>
              <h2 className="mt-6 text-2xl!">{title}</h2>
              <p className="mt-3 text-sm leading-relaxed opacity-75">{body}</p>
              <span
                aria-hidden="true"
                className="mt-6 block h-[3px] w-8 bg-volt transition-all duration-500 group-hover:w-full"
              />
            </article>
          ))}
        </section>

        <footer className="eyebrow flex flex-wrap items-center justify-between gap-4 py-10 opacity-60">
          <Suspense fallback={<p>Checking backend…</p>}>
            <BackendStatus />
          </Suspense>
          <span>© ScoutSphere</span>
        </footer>
      </main>
    </div>
  );
}
