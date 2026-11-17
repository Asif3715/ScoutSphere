// Browser code uses the public URL; server components inside Docker reach the
// backend over the compose network via INTERNAL_API_URL.
export const API_URL =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export type ReadinessResponse = {
  status: "ok" | "degraded";
  checks: Record<string, string>;
};

export async function fetchReadiness(): Promise<ReadinessResponse> {
  const res = await fetch(`${API_URL}/api/v1/health/ready`, {
    cache: "no-store",
  });
  // 503 still carries a valid body describing which dependency is down
  if (res.status !== 200 && res.status !== 503) {
    throw new Error(`Unexpected status ${res.status}`);
  }
  return res.json();
}
