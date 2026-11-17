"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Card, ErrorText, Stat } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import type { Dashboard } from "@/lib/types";

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
          <Card>
            <h2 className="font-semibold">Get started</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {can("clubs:manage") && (
                <li>
                  <Link className="text-teal-600 underline" href="/clubs/new">
                    Register a club
                  </Link>
                </li>
              )}
              {can("members:manage") && (
                <li>
                  <Link className="text-teal-600 underline" href="/members">
                    Invite scouts, coaches and recruitment managers
                  </Link>
                </li>
              )}
              <li className="opacity-70">
                Players, scouts and matches arrive in the next phases.
              </li>
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}
