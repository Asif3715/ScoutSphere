"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { LogoMark, Wordmark } from "@/components/brand/brand";
import { NavProgress } from "@/components/layout/nav-progress";
import { NotificationBell } from "@/components/layout/notification-bell";
import { FlashBanner } from "@/components/ui/flash-banner";
import { PersonAvatar } from "@/components/ui/person";
import { useAuth } from "@/lib/auth";
import { setFlash } from "@/lib/flash";

/** A light frame for player accounts: no club navigation, just their own space. */
export function PlayerShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  return (
    <div className="min-h-screen">
      <NavProgress />
      <header className="sticky top-0 z-20 border-b border-white/10 bg-dugout text-dugout-ink">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 md:px-8">
          <Link href="/player" className="flex items-center gap-2.5">
            <LogoMark className="h-8 w-8 text-dugout-ink" />
            <Wordmark />
          </Link>
          <div className="flex items-center gap-3">
            <span className="eyebrow hidden rounded-[2px] bg-volt px-2 py-1 text-volt-ink sm:inline">
              Player account
            </span>
            <NotificationBell />
            {user && (
              <span className="hidden items-center gap-2 text-sm sm:flex">
                <PersonAvatar name={user.full_name} size="sm" />
                {user.full_name}
              </span>
            )}
            <button
              onClick={async () => {
                await logout();
                setFlash({ kind: "info", text: "You've been signed out." });
                router.replace("/login");
              }}
              className="eyebrow text-dugout-ink/70 underline-offset-4 transition-colors hover:text-volt hover:underline"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main
        key={pathname}
        className="page-reveal mx-auto w-full max-w-5xl min-w-0 px-4 py-6 md:px-8 md:py-10"
      >
        <FlashBanner className="mb-6" />
        {children}
      </main>
    </div>
  );
}
