import { API_URL } from "@/lib/api";

export type User = {
  id: string;
  email: string;
  full_name: string;
  account_type: string;
  platform_role: string | null;
  is_active: boolean;
};

export type TokenResponse = {
  access_token: string;
  expires_in: number;
  user: User;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: { field: string; message: string }[],
  ) {
    super(message);
  }
}

// The access token lives only in memory (never localStorage). The refresh token is an
// httpOnly cookie the browser sends automatically; JS cannot read it.
let accessToken: string | null = null;
let activeOrgId: string | null = null;
let refreshInFlight: Promise<TokenResponse | null> | null = null;

export const setAccessToken = (t: string | null) => (accessToken = t);
export const getAccessToken = () => accessToken;
export const setActiveOrg = (id: string | null) => (activeOrgId = id);

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const e = body.error ?? {};
    return new ApiError(
      res.status,
      e.code ?? "error",
      e.message ?? res.statusText,
      e.details,
    );
  } catch {
    return new ApiError(res.status, "error", res.statusText);
  }
}

/** Exchanges the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) {
          accessToken = null;
          return null;
        }
        const data: TokenResponse = await res.json();
        accessToken = data.access_token;
        return data;
      } catch {
        accessToken = null;
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { json?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { json, auth = true, ...rest } = init;

  const send = () => {
    const headers = new Headers(rest.headers);
    if (json !== undefined) headers.set("Content-Type", "application/json");
    if (auth && accessToken)
      headers.set("Authorization", `Bearer ${accessToken}`);
    if (auth && activeOrgId) headers.set("X-Organization-Id", activeOrgId);
    return fetch(`${API_URL}/api/v1${path}`, {
      ...rest,
      headers,
      credentials: "include",
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  };

  let res = await send();
  if (res.status === 401 && auth) {
    // Access token expired: try one silent refresh, then replay the request once.
    if (await refreshSession()) res = await send();
  }
  if (!res.ok) throw await parseError(res);
  return res.status === 204 ? (undefined as T) : res.json();
}
