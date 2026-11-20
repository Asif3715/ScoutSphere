// Browser code uses the public URL; server components inside Docker reach the
// backend over the compose network via INTERNAL_API_URL.
const CONFIGURED_API_URL =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

/**
 * Browsers treat `localhost` and `127.0.0.1` as different sites. If the page is opened on one
 * loopback name while the API is configured on the other, the session cookie would be
 * cross-site and silently dropped, so the API is addressed with the page's own loopback name.
 * Any non-loopback configuration (staging, production) is returned untouched.
 */
export function resolveApiUrl(configured: string, pageHost?: string): string {
  if (!pageHost || !LOOPBACK.has(pageHost)) return configured;
  try {
    const url = new URL(configured);
    if (!LOOPBACK.has(url.hostname) || url.hostname === pageHost)
      return configured;
    url.hostname = pageHost;
    return url.origin;
  } catch {
    return configured;
  }
}

export const API_URL =
  typeof window === "undefined"
    ? CONFIGURED_API_URL
    : resolveApiUrl(CONFIGURED_API_URL, window.location.hostname);

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
