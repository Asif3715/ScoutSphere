"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { ErrorText, Stat } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import type { Dashboard } from "@/lib/types";

const QUICK = [
  {
    href: "/players",
    title: "Players",
    body: "Search the player database and open dossiers.",
    permission: "players:read",
  },
  {
    href: "/assignments",
    title: "Assignments",
    body: "Who is watching which match, and by when.",
    permission: "assignments:read",
  },
  {
    href: "/reports",
    title: "Reports",
    body: "Write, submit and review scouting reports.",
    permission: "reports:read",
  },
  {
    href: "/recruitment",
    title: "Recruitment",
    body: "Requirements, matching players and the pipeline.",
    permission: "recruitment:read",
  },
  {
    href: "/shortlists",
    title: "Shortlists",
    body: "Your private lists, and those shared with you.",
    permission: "recruitment:read",
  },
  {
    href: "/members",
    title: "Members",
    body: "Invite scouts, coaches and recruitment managers.",
    permission: "members:manage",
  },
  {
    href: "/clubs/new",
    title: "Register a club",
    body: "Add a club your organization manages.",
    permission: "clubs:manage",
  },
] as const;

export default function DashboardPage() {
  const { user, activeOrgId, can } = useAuth();
  const { data, error, isLoading } = useQuery({
    queryKey: ["dashboard", activeOrgId],
    queryFn: () =>
      apiFetch<Dashboard>(`/organizations/${activeOrgId}/dashboard`),
    enabled: !!activeOrgId,
  });

  if (!activeOrgId) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Platform</h1>
        <p className="text-sm opacity-70">
          Signed in as {user?.full_name}
          {user?.platform_role ? ` (${user.platform_role})` : ""}. Platform
          administration screens arrive in a later phase.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="eyebrow mb-3 text-link">
          Welcome back, {user?.full_name?.split(" ")[0]}
        </p>
        <h1 className="text-2xl font-bold">
          {data?.organization.name ?? "Overview"}
        </h1>
        {data?.organization.description && (
          <p className="text-sm opacity-70">{data.organization.description}</p>
        )}
      </header>
      {isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{error?.message}</ErrorText>
      {data && (
        <>
          <section
            className="grid gap-4 sm:grid-cols-3"
            aria-label="Organization summary"
          >
            <Stat label="Clubs" value={data.clubs} />
            <Stat label="Members" value={data.members} />
            <Stat
              label="Pending invitations"
              value={data.pending_invitations}
            />
          </section>
          <section aria-label="Quick actions">
            <h3 className="mb-3 opacity-60">Quick actions</h3>
            <ul className="grid overflow-hidden rounded-[3px] border-t border-l border-line sm:grid-cols-2 lg:grid-cols-3">
              {QUICK.filter((q) => can(q.permission)).map((q, i) => (
                <li key={q.href} className="border-r border-b border-line">
                  <Link
                    href={q.href}
                    className="group flex h-full flex-col bg-surface p-5 transition-colors hover:bg-paper"
                  >
                    <span className="font-mono text-xs text-link">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="font-display mt-4 text-2xl leading-none font-bold uppercase">
                      {q.title}
                    </span>
                    <span className="mt-2 text-sm opacity-70">{q.body}</span>
                    <span
                      aria-hidden="true"
                      className="mt-4 block h-[3px] w-6 bg-volt transition-all duration-500 group-hover:w-full"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
