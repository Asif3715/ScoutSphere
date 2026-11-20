"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { LogoMark, Wordmark } from "@/components/brand/brand";
import { NotificationBell } from "@/components/layout/notification-bell";
import { FlashBanner } from "@/components/ui/flash-banner";
import { PersonAvatar, RoleBadge, roleName } from "@/components/ui/person";
import { useAuth } from "@/lib/auth";
import { setFlash } from "@/lib/flash";

// Navigation is role-aware: an item shows only if the user holds its permission.
// This is a usability nicety; the backend independently authorizes every request.
const NAV = [
  {
    group: "Club",
    items: [
      { href: "/dashboard", label: "Overview", permission: null },
      { href: "/clubs", label: "Clubs", permission: "clubs:read" },
      { href: "/teams", label: "Teams", permission: "clubs:read" },
      { href: "/players", label: "Players", permission: "players:read" },
    ],
  },
  {
    group: "Scouting",
    items: [
      { href: "/scouts", label: "Scouts", permission: "scouts:read" },
      {
        href: "/assignments",
        label: "Assignments",
        permission: "assignments:read",
      },
      { href: "/reports", label: "Reports", permission: "reports:read" },
    ],
  },
  {
    group: "Recruitment",
    items: [
      {
        href: "/recruitment",
        label: "Pipeline",
        permission: "recruitment:read",
      },
      {
        href: "/shortlists",
        label: "Shortlists",
        permission: "recruitment:read",
      },
    ],
  },
  {
    group: "Fixtures",
    items: [
      {
        href: "/competitions",
        label: "Competitions",
        permission: "matches:read",
      },
      { href: "/matches", label: "Matches", permission: "matches:read" },
    ],
  },
  {
    group: "Admin",
    items: [{ href: "/members", label: "Members", permission: "members:read" }],
  },
] as const;

function today() {
  return new Date()
    .toLocaleDateString("en-GB", {
      weekday: "short",
      day: "2-digit",
      month: "short",
    })
    .toUpperCase();
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, memberships, activeOrgId, selectOrg, logout, can } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const active = memberships.find((m) => m.organization_id === activeOrgId);
  // On phones the sidebar is a slide-over drawer instead of a permanent column.
  const [menuOpen, setMenuOpen] = useState(false);

  let n = 0;
  const groups = NAV.map((g) => ({
    group: g.group,
    items: g.items
      .filter((i) => i.permission === null || can(i.permission))
      .map((i) => ({ ...i, n: ++n })),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="flex min-h-screen">
      {menuOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-30 bg-dugout/70 backdrop-blur-sm md:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside
        id="main-nav"
        className={`w-64 shrink-0 bg-dugout text-dugout-ink ${
          menuOpen ? "fixed inset-y-0 left-0 z-40 flex" : "hidden"
        } flex-col md:sticky md:top-0 md:z-auto md:flex md:h-screen`}
      >
        {/* floodlight glow in the dugout corner */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 [background:radial-gradient(420px_260px_at_0%_0%,rgb(198_244_50/0.10),transparent_70%)]"
        />
        <Link
          href="/dashboard"
          className="relative flex items-center gap-2.5 px-5 pt-6 pb-5"
        >
          <LogoMark className="h-9 w-9 text-dugout-ink" />
          <Wordmark />
        </Link>
        <nav
          className="relative flex-1 space-y-5 overflow-y-auto px-3 pb-6 [scrollbar-color:rgb(255_255_255/0.14)_transparent] [scrollbar-width:thin]"
          aria-label="Main"
        >
          {groups.map((g) => (
            <div key={g.group}>
              <p className="eyebrow px-2 pb-1.5 text-dugout-ink/40">
                {g.group}
              </p>
              <ul>
                {g.items.map((item) => {
                  const current =
                    pathname === item.href ||
                    pathname.startsWith(`${item.href}/`);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setMenuOpen(false)}
                        aria-current={current ? "page" : undefined}
                        className={`group relative flex items-center gap-3 rounded-[2px] px-2 py-1.5 text-[0.95rem] transition-colors ${
                          current
                            ? "bg-volt/10 text-volt"
                            : "text-dugout-ink/75 hover:bg-white/5 hover:text-dugout-ink"
                        }`}
                      >
                        <span
                          aria-hidden="true"
                          className={`absolute top-1/2 left-0 h-5 w-[3px] -translate-y-1/2 bg-volt transition-transform duration-300 ${
                            current
                              ? "scale-y-100"
                              : "scale-y-0 group-hover:scale-y-50"
                          }`}
                        />
                        <span
                          aria-hidden="true"
                          className="w-5 pl-1 font-mono text-[0.62rem] tabular-nums opacity-50"
                        >
                          {String(item.n).padStart(2, "0")}
                        </span>
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
        <div className="relative border-t border-white/10 px-5 py-4">
          <div className="flex items-center gap-3">
            {user && <PersonAvatar name={user.full_name} size="md" />}
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">
                {user?.full_name}
              </p>
              <p className="eyebrow mt-0.5 truncate text-volt/80">
                {active
                  ? roleName(active.role)
                  : (user?.platform_role ?? "member")}
              </p>
            </div>
          </div>
          <button
            onClick={async () => {
              await logout();
              setFlash({ kind: "info", text: "You've been signed out." });
              router.replace("/login");
            }}
            className="eyebrow mt-3 text-dugout-ink/60 underline-offset-4 transition-colors hover:text-volt hover:underline"
          >
            Sign out →
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-paper/85 px-4 py-3 backdrop-blur-md md:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="btn btn-secondary px-2.5 md:hidden"
              aria-label="Open menu"
              aria-expanded={menuOpen}
              aria-controls="main-nav"
              onClick={() => setMenuOpen((o) => !o)}
            >
              <span aria-hidden="true" className="block w-4 space-y-1">
                <span className="block h-px bg-current" />
                <span className="block h-px bg-current" />
                <span className="block h-px bg-current" />
              </span>
            </button>
            {memberships.length > 0 ? (
              <>
                <label htmlFor="org-switch" className="sr-only">
                  Active organization
                </label>
                <select
                  id="org-switch"
                  value={activeOrgId ?? ""}
                  onChange={(e) => {
                    selectOrg(e.target.value);
                    router.push("/dashboard");
                  }}
                  className="font-display max-w-[46vw] min-w-0 cursor-pointer truncate border-0 bg-transparent pr-1 text-xl font-bold uppercase [font-variation-settings:'opsz'_40] focus:ring-0 sm:max-w-[60vw]"
                >
                  {memberships.map((m) => (
                    <option key={m.organization_id} value={m.organization_id}>
                      {m.organization_name}
                    </option>
                  ))}
                </select>
                {active && (
                  <span
                    className="flex shrink-0 items-center gap-2"
                    aria-label={`Your role here: ${roleName(active.role)}`}
                  >
                    <span
                      aria-hidden="true"
                      className="hidden h-5 w-px bg-line-strong sm:block"
                    />
                    <span className="eyebrow hidden opacity-55 lg:inline">
                      You are
                    </span>
                    <RoleBadge
                      role={active.role}
                      className="sm:hidden"
                      compact
                    />
                    <RoleBadge
                      role={active.role}
                      className="hidden px-2! py-0.5! sm:inline-flex"
                    />
                  </span>
                )}
              </>
            ) : (
              <span className="eyebrow opacity-70">No organization</span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="eyebrow hidden items-center gap-2 opacity-60 sm:flex">
              <span
                aria-hidden="true"
                className="live-dot h-1.5 w-1.5 rounded-full bg-ok"
              />
              Matchday · {today()}
            </span>
            <NotificationBell />
          </div>
        </header>
        <main
          key={pathname}
          className="page-reveal mx-auto w-full max-w-6xl min-w-0 flex-1 px-4 py-6 md:px-8 md:py-10"
        >
          <FlashBanner className="mb-6" />
          {children}
        </main>
      </div>
    </div>
  );
}
