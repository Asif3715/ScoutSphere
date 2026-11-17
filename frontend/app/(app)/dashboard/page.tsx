"use client";

import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const { user, memberships, activeOrgId, selectOrg, logout } = useAuth();
  const router = useRouter();
  const active = memberships.find((m) => m.organization_id === activeOrgId);

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm opacity-70">
            Signed in as {user?.full_name} ({user?.email})
          </p>
        </div>
        <button
          onClick={async () => {
            await logout();
            router.replace("/login");
          }}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          Sign out
        </button>
      </header>

      {user?.platform_role && (
        <p className="rounded-md bg-teal-50 p-3 text-sm text-teal-900">
          Platform role: <strong>{user.platform_role}</strong>
        </p>
      )}

      {memberships.length === 0 ? (
        <p className="text-sm">
          You do not belong to any organization yet. Organization creation and
          invitations arrive in the next phase.
        </p>
      ) : (
        <section className="space-y-2">
          <label htmlFor="org" className="block text-sm font-medium">
            Active organization
          </label>
          <select
            id="org"
            value={activeOrgId ?? ""}
            onChange={(e) => selectOrg(e.target.value || null)}
            className="rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm"
          >
            {memberships.map((m) => (
              <option key={m.organization_id} value={m.organization_id}>
                {m.organization_name} — {m.role}
              </option>
            ))}
          </select>
          {active && (
            <p className="text-xs opacity-70">
              {active.permissions.length} permissions in this organization
            </p>
          )}
        </section>
      )}
    </main>
  );
}
