"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/lib/auth";

/** Client-side route guard: UX only. The backend independently authorizes every request. */
export function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading, memberships } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const needsOrg =
    !!user && memberships.length === 0 && pathname !== "/onboarding";

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    else if (needsOrg && !user?.platform_role) router.replace("/onboarding");
  }, [loading, user, needsOrg, router]);

  if (loading || !user || (needsOrg && !user.platform_role)) {
    return (
      <main className="p-10" aria-busy="true">
        Loading…
      </main>
    );
  }
  return <AppShell>{children}</AppShell>;
}
