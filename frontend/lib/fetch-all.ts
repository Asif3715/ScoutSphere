import { apiFetch } from "@/lib/http";
import type { Page } from "@/lib/types";

/**
 * Every item of a paginated list, for pickers and dropdowns. The API serves at most 100 per
 * page, so a single request would silently drop the rest. Stops at `max` as a safety net.
 */
export async function fetchAll<T>(path: string, max = 2000): Promise<Page<T>> {
  const sep = path.includes("?") ? "&" : "?";
  const base = /[?&]page_size=/.test(path)
    ? path
    : `${path}${sep}page_size=100`;
  const items: T[] = [];
  let total = 0;
  for (let page = 1; ; page++) {
    const res = await apiFetch<Page<T>>(`${base}&page=${page}`);
    items.push(...res.items);
    total = res.total;
    if (res.items.length === 0 || items.length >= total || items.length >= max)
      break;
  }
  return { items, total, page: 1, page_size: items.length };
}
