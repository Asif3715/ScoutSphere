import { Suspense } from "react";

import { fetchReadiness, type ReadinessResponse } from "@/lib/api";

async function BackendStatus() {
  let readiness: ReadinessResponse | null = null;
  try {
    readiness = await fetchReadiness();
  } catch {
    readiness = null;
  }

  return (
    <ul className="mt-6 space-y-2" data-testid="status-list">
      <li>Backend: {readiness ? readiness.status : "unreachable"}</li>
      {readiness &&
        Object.entries(readiness.checks).map(([name, state]) => (
          <li key={name}>
            {name}: {state}
          </li>
        ))}
    </ul>
  );
}

export default function Home() {
  return (
    <main className="mx-auto max-w-xl p-10">
      <h1 className="text-3xl font-bold">ScoutSphere</h1>
      <p className="mt-2 text-sm opacity-70">Phase 0 — system status</p>
      <Suspense fallback={<p className="mt-6">Checking backend…</p>}>
        <BackendStatus />
      </Suspense>
    </main>
  );
}
