"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { NotificationBell } from "@/components/layout/notification-bell";
import { useAuth } from "@/lib/auth";
import { ROLE_LABELS } from "@/lib/types";

// Navigation is role-aware: an item shows only if the user holds its permission.
// This is a usability nicety; the backend independently authorizes every request.
const NAV = [
  { href: "/dashboard", label: "Overview", permission: null },
  { href: "/clubs", label: "Clubs", permission: "clubs:read" },
  { href: "/teams", label: "Teams", permission: "clubs:read" },
  { href: "/players", label: "Players", permission: "players:read" },
  { href: "/scouts", label: "Scouts", permission: "scouts:read" },
  {
    href: "/assignments",
    label: "Assignments",
    permission: "assignments:read",
  },
  { href: "/reports", label: "Reports", permission: "reports:read" },
  { href: "/competitions", label: "Competitions", permission: "matches:read" },
  { href: "/matches", label: "Matches", permission: "matches:read" },
  { href: "/members", label: "Members", permission: "members:read" },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, memberships, activeOrgId, selectOrg, logout, can } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const active = memberships.find((m) => m.organization_id === activeOrgId);
  // On phones the sidebar is a slide-over drawer instead of a permanent 224px column.
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {menuOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside
        id="main-nav"
        className={`w-56 shrink-0 border-r border-slate-200 bg-background p-4 dark:border-slate-800 ${
          menuOpen
            ? "fixed inset-y-0 left-0 z-40 block overflow-y-auto"
            : "hidden"
        } md:static md:z-auto md:block`}
      >
        <Link href="/dashboard" className="block text-lg font-bold">
          ScoutSphere
        </Link>
        <nav className="mt-6 space-y-1" aria-label="Main">
          {NAV.filter((i) => i.permission === null || can(i.permission)).map(
            (item) => {
              const current =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMenuOpen(false)}
                  aria-current={current ? "page" : undefined}
                  className={`block rounded-md px-3 py-2 text-sm ${
                    current
                      ? "bg-teal-600 text-white"
                      : "hover:bg-slate-100 dark:hover:bg-slate-800"
                  }`}
                >
                  {item.label}
                </Link>
              );
            },
          )}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 md:px-6 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1 text-sm md:hidden"
              aria-label="Open menu"
              aria-expanded={menuOpen}
              aria-controls="main-nav"
              onClick={() => setMenuOpen((o) => !o)}
            >
              ☰
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
                  className="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm"
                >
                  {memberships.map((m) => (
                    <option key={m.organization_id} value={m.organization_id}>
                      {m.organization_name}
                    </option>
                  ))}
                </select>
                {active && (
                  <span className="text-xs opacity-70">
                    {ROLE_LABELS[active.role] ?? active.role}
                  </span>
                )}
              </>
            ) : (
              <span className="text-sm opacity-70">No organization</span>
            )}
          </div>
          <div className="flex items-center gap-3 text-sm">
            <NotificationBell />
            <span className="hidden opacity-70 sm:inline">
              {user?.full_name}
            </span>
            <button
              onClick={async () => {
                await logout();
                router.replace("/login");
              }}
              className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
