import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAll } from "@/lib/fetch-all";
import { setAccessToken, setActiveOrg } from "@/lib/http";

const page = (items: number[], total: number) => ({
  ok: true,
  status: 200,
  json: async () => ({ items, total, page: 1, page_size: 100 }),
});

beforeEach(() => {
  setAccessToken("t");
  setActiveOrg("org");
});
afterEach(() => vi.unstubAllGlobals());

describe("fetchAll", () => {
  it("follows pages until it has everything", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(page([1, 2], 5))
      .mockResolvedValueOnce(page([3, 4], 5))
      .mockResolvedValueOnce(page([5], 5));
    vi.stubGlobal("fetch", f);
    const all = await fetchAll<number>("/scouts?status=active");
    expect(all.items).toEqual([1, 2, 3, 4, 5]);
    expect(all.total).toBe(5);
    expect(f.mock.calls[0][0]).toContain(
      "/scouts?status=active&page_size=100&page=1",
    );
    expect(f.mock.calls[2][0]).toContain("page=3");
  });

  it("stops at the safety limit", async () => {
    const f = vi.fn().mockResolvedValue(page([1, 2, 3], 10_000));
    vi.stubGlobal("fetch", f);
    const all = await fetchAll<number>("/players", 6);
    expect(all.items).toHaveLength(6);
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("stops on an empty page even if the total disagrees", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(page([1], 50))
      .mockResolvedValueOnce(page([], 50));
    vi.stubGlobal("fetch", f);
    expect((await fetchAll<number>("/clubs")).items).toEqual([1]);
  });
});
