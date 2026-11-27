import type { KeyboardEvent } from "react";

/**
 * Keyboard support for a `role="tablist"` (WAI-ARIA tabs pattern): arrow keys move between
 * tabs and select them, Home/End jump to the ends. Pair with `tabIndex={selected ? 0 : -1}`
 * on each tab so Tab moves into the list once, onto the selected tab.
 */
export function tabKeys(e: KeyboardEvent<HTMLElement>) {
  const tabs = Array.from(
    e.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]'),
  );
  const i = tabs.indexOf(document.activeElement as HTMLElement);
  if (i < 0) return;
  const last = tabs.length - 1;
  const next =
    e.key === "ArrowRight" || e.key === "ArrowDown"
      ? i === last
        ? 0
        : i + 1
      : e.key === "ArrowLeft" || e.key === "ArrowUp"
        ? i === 0
          ? last
          : i - 1
        : e.key === "Home"
          ? 0
          : e.key === "End"
            ? last
            : -1;
  if (next < 0) return;
  e.preventDefault();
  tabs[next].focus();
  tabs[next].click();
}
