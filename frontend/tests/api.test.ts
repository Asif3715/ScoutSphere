import { afterEach, expect, it, vi } from "vitest";

import { fetchReadiness } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

it("returns the body for a healthy backend", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ status: "ok", checks: { postgres: "ok", redis: "ok" } }),
    }),
  );
  expect((await fetchReadiness()).status).toBe("ok");
});

it("returns the degraded body on 503", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      status: 503,
      json: async () => ({ status: "degraded", checks: { postgres: "unavailable" } }),
    }),
  );
  expect((await fetchReadiness()).status).toBe("degraded");
});

it("throws on unexpected status", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 500, json: async () => ({}) }));
  await expect(fetchReadiness()).rejects.toThrow();
});
