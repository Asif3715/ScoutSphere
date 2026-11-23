"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

type Phase = "idle" | "loading" | "done";

/** The internal path a click on this anchor would navigate to, or null if it isn't one. */
function internalTarget(a: HTMLAnchorElement): string | null {
  if (a.target && a.target !== "_self") return null;
  if (a.hasAttribute("download")) return null;
  const url = new URL(a.href, window.location.href);
  if (url.origin !== window.location.origin) return null;
  // a hash-only change stays on the page
  if (
    url.pathname === window.location.pathname &&
    url.search === window.location.search
  )
    return null;
  return url.pathname;
}

/**
 * A thin bar across the top of the screen that starts the moment any internal link is
 * clicked and finishes when the new page arrives, so a click never feels ignored.
 * (Next.js has no router events in the App Router, so this listens for the click itself.)
 */
export function NavProgress() {
  const pathname = usePathname();
  const [phase, setPhase] = useState<Phase>("idle");
  const [seenPath, setSeenPath] = useState(pathname);

  // The route changed: finish the bar.
  if (seenPath !== pathname) {
    setSeenPath(pathname);
    if (phase === "loading") setPhase("done");
  }

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      // (no defaultPrevented check: <Link> prevents default itself to navigate client-side)
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
        return;
      const a = (e.target as Element | null)?.closest?.("a[href]");
      if (!(a instanceof HTMLAnchorElement)) return;
      if (internalTarget(a) !== null) setPhase("loading");
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  useEffect(() => {
    if (phase === "done") {
      const t = setTimeout(() => setPhase("idle"), 450);
      return () => clearTimeout(t);
    }
    if (phase === "loading") {
      // never leave the bar hanging if a navigation is cancelled or fails
      const t = setTimeout(() => setPhase("idle"), 15_000);
      return () => clearTimeout(t);
    }
  }, [phase]);

  return (
    <div
      aria-hidden="true"
      data-phase={phase}
      className="nav-progress pointer-events-none fixed inset-x-0 top-0 z-[70] h-[3px]"
    >
      <div className="nav-progress-bar h-full bg-volt" />
    </div>
  );
}
