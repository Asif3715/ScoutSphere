"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { PlayerShell } from "@/components/layout/player-shell";
import { useAuth } from "@/lib/auth";

/** Client-side route guard: UX only. The backend independently authorizes every request. */
export function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading, memberships } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  // A player account is a person, not a club: it has its own portal and no organization.
  const isPlayer = user?.account_type === "player" && memberships.length === 0;
  const inPortal = pathname === "/player" || pathname.startsWith("/player/");
  const needsOrg =
    !!user &&
    !isPlayer &&
    memberships.length === 0 &&
    pathname !== "/onboarding";
  const toPortal =
    isPlayer && !inPortal && !pathname.startsWith("/notifications");

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    else if (toPortal) router.replace("/player");
    else if (needsOrg && !user?.platform_role) router.replace("/onboarding");
  }, [loading, user, needsOrg, toPortal, router]);

  if (loading || !user || toPortal || (needsOrg && !user.platform_role)) {
    return (
      <main className="p-10" aria-busy="true">
        Loading…
      </main>
    );
  }
  if (isPlayer) return <PlayerShell>{children}</PlayerShell>;
  return <AppShell>{children}</AppShell>;
}
