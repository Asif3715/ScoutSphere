import { afterEach, expect, it, vi } from "vitest";

import { fetchReadiness } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

it("returns the body for a healthy backend", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({
        status: "ok",
        checks: { postgres: "ok", redis: "ok" },
      }),
    }),
  );
  expect((await fetchReadiness()).status).toBe("ok");
});

it("returns the degraded body on 503", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      status: 503,
      json: async () => ({
        status: "degraded",
        checks: { postgres: "unavailable" },
      }),
    }),
  );
  expect((await fetchReadiness()).status).toBe("degraded");
});

it("throws on unexpected status", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status: 500, json: async () => ({}) }),
  );
  await expect(fetchReadiness()).rejects.toThrow();
});

import { resolveApiUrl } from "@/lib/api";

it("follows the page's loopback name so the session cookie stays same-site", () => {
  expect(resolveApiUrl("http://localhost:8000", "127.0.0.1")).toBe(
    "http://127.0.0.1:8000",
  );
  expect(resolveApiUrl("http://127.0.0.1:8000", "localhost")).toBe(
    "http://localhost:8000",
  );
  expect(resolveApiUrl("http://localhost:8000", "localhost")).toBe(
    "http://localhost:8000",
  );
});

it("never rewrites a real deployment address", () => {
  expect(resolveApiUrl("https://api.scoutsphere.app", "127.0.0.1")).toBe(
    "https://api.scoutsphere.app",
  );
  expect(resolveApiUrl("http://localhost:8000", "app.example.com")).toBe(
    "http://localhost:8000",
  );
  expect(resolveApiUrl("http://localhost:8000", undefined)).toBe(
    "http://localhost:8000",
  );
});
