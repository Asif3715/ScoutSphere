"use client";

import { useEffect, useState } from "react";

import { takeFlash, type Flash } from "@/lib/flash";

/** Shows a one-shot message left by the previous page (e.g. "Account created"). */
export function FlashBanner({ className = "" }: { className?: string }) {
  const [flash, setFlash] = useState<Flash | null>(null);

  useEffect(() => {
    // Read once after mount (sessionStorage is browser-only). A strict-mode re-run finds the
    // message already taken and leaves the shown one alone.
    const pending = takeFlash();
    if (!pending) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time read of browser storage
    setFlash(pending);
    const t = window.setTimeout(() => setFlash(null), 9000);
    return () => window.clearTimeout(t);
  }, []);

  if (!flash) return null;
  return (
    <div
      role="status"
      className={`flex items-start justify-between gap-3 rounded-[2px] border-l-4 px-4 py-3 text-sm ${
        flash.kind === "success"
          ? "border-ok bg-ok-soft"
          : "border-info bg-info-soft"
      } ${className}`}
    >
      <p className="flex items-start gap-2">
        <span
          aria-hidden="true"
          className={flash.kind === "success" ? "text-ok" : "text-info"}
        >
          {flash.kind === "success" ? "✓" : "i"}
        </span>
        {flash.text}
      </p>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => setFlash(null)}
        className="opacity-60 hover:opacity-100"
      >
        ×
      </button>
    </div>
  );
}
