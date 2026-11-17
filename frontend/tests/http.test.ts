import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiFetch,
  ApiError,
  getAccessToken,
  setAccessToken,
  setActiveOrg,
} from "@/lib/http";

const json = (status: number, body: unknown) => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: "x",
  json: async () => body,
});

beforeEach(() => {
  setAccessToken("old");
  setActiveOrg("org-1");
});
afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("sends bearer token and organization header", async () => {
    const f = vi.fn().mockResolvedValue(json(200, { ok: 1 }));
    vi.stubGlobal("fetch", f);
    await apiFetch("/thing");
    const headers = f.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer old");
    expect(headers.get("X-Organization-Id")).toBe("org-1");
    expect(f.mock.calls[0][1].credentials).toBe("include");
  });

  it("refreshes once on 401 and replays the request", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(
        json(401, { error: { code: "invalid_token", message: "expired" } }),
      )
      .mockResolvedValueOnce(
        json(200, { access_token: "new", expires_in: 900, user: {} }),
      )
      .mockResolvedValueOnce(json(200, { data: 42 }));
    vi.stubGlobal("fetch", f);
    await expect(apiFetch("/thing")).resolves.toEqual({ data: 42 });
    expect(getAccessToken()).toBe("new");
    expect(f).toHaveBeenCalledTimes(3);
  });

  it("surfaces the 401 when refresh fails and clears the token", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(
        json(401, { error: { code: "invalid_token", message: "expired" } }),
      )
      .mockResolvedValueOnce(
        json(401, { error: { code: "invalid_refresh_token", message: "no" } }),
      )
      .mockResolvedValueOnce(
        json(401, { error: { code: "invalid_token", message: "expired" } }),
      );
    vi.stubGlobal("fetch", f);
    await expect(apiFetch("/thing")).rejects.toMatchObject({
      status: 401,
      code: "invalid_token",
    });
    expect(getAccessToken()).toBeNull();
  });

  it("does not try to refresh for unauthenticated calls such as login", async () => {
    const f = vi
      .fn()
      .mockResolvedValue(
        json(401, { error: { code: "invalid_credentials", message: "bad" } }),
      );
    vi.stubGlobal("fetch", f);
    const err = await apiFetch("/auth/login", {
      method: "POST",
      json: {},
      auth: false,
    }).catch((e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("invalid_credentials");
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("returns undefined for 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(204, null)));
    await expect(
      apiFetch("/auth/logout", { method: "POST" }),
    ).resolves.toBeUndefined();
  });
});
