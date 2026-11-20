/**
 * One-shot messages that survive a client-side redirect ("Account created", "Signed out").
 * Stored in sessionStorage so they never outlive the tab and never travel in a URL.
 */
export type Flash = { kind: "success" | "info"; text: string };

const KEY = "scoutsphere:flash";

export function setFlash(flash: Flash): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(flash));
  } catch {}
}

/** Returns the pending message and removes it, so it is shown exactly once. */
export function takeFlash(): Flash | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    return typeof value?.text === "string" ? (value as Flash) : null;
  } catch {
    return null;
  }
}
