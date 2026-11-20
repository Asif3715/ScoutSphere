"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { Field } from "@/components/auth/field";
import {
  PageHeader,
  SearchInput,
  SkeletonRows,
  TableCard,
  TableMessage,
} from "@/components/ui/data-table";
import { CheckIcon, CopyIcon, MailIcon } from "@/components/ui/icons";
import {
  PersonAvatar,
  ROLE_INFO,
  RoleBadge,
  roleName,
} from "@/components/ui/person";
import { Button, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { deadlineLabel, shortDate, timeAgo } from "@/lib/format";
import { ApiError, apiFetch } from "@/lib/http";
import { inviteSchema, type InviteValues } from "@/lib/schemas";
import { ORG_ROLES, type Invitation, type Member } from "@/lib/types";

const ROLE_ORDER = new Map<string, number>(ORG_ROLES.map((r, i) => [r, i]));

function byRoleThenName(a: Member, b: Member) {
  return (
    (ROLE_ORDER.get(a.role) ?? 99) - (ROLE_ORDER.get(b.role) ?? 99) ||
    a.full_name.localeCompare(b.full_name)
  );
}

function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex gap-2">
      <input
        readOnly
        aria-label="Invitation link"
        value={url}
        onFocus={(e) => e.currentTarget.select()}
        className="field-input min-w-0 flex-1 font-mono text-xs"
      />
      <Button
        type="button"
        variant="secondary"
        className="h-9"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          } catch {
            /* clipboard blocked: the field is selectable as a fallback */
          }
        }}
      >
        {copied ? (
          <CheckIcon className="h-4 w-4" />
        ) : (
          <CopyIcon className="h-4 w-4" />
        )}
        {copied ? "Copied" : "Copy"}
      </Button>
    </div>
  );
}

export default function MembersPage() {
  const { activeOrgId, user, can, memberships } = useAuth();
  const queryClient = useQueryClient();
  const manage = can("members:manage");
  const active = memberships.find((m) => m.organization_id === activeOrgId);
  const myRole = active?.role;
  // Only owners may grant or change owner access (the backend enforces this too).
  const assignable = ORG_ROLES.filter(
    (r) => r !== "club_owner" || myRole === "club_owner",
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastInvite, setLastInvite] = useState<Invitation | null>(null);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");

  const base = `/organizations/${activeOrgId}`;
  const members = useQuery({
    queryKey: ["members", activeOrgId],
    queryFn: () => apiFetch<Member[]>(`${base}/members`),
    enabled: !!activeOrgId,
  });
  const invitations = useQuery({
    queryKey: ["invitations", activeOrgId],
    queryFn: () => apiFetch<Invitation[]>(`${base}/invitations`),
    enabled: !!activeOrgId && manage,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["members", activeOrgId] });
    queryClient.invalidateQueries({ queryKey: ["invitations", activeOrgId] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const onError = (e: Error) =>
    setActionError(e instanceof ApiError ? e.message : "Request failed");

  const changeRole = useMutation({
    mutationFn: (v: { id: string; role: string }) =>
      apiFetch(`${base}/members/${v.id}`, {
        method: "PATCH",
        json: { role: v.role },
      }),
    onSuccess: refresh,
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`${base}/members/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError,
  });
  const revoke = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`${base}/invitations/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError,
  });

  const {
    register,
    handleSubmit,
    reset,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "scout" },
  });
  const chosenRole = useWatch({ control, name: "role" });

  const invite = handleSubmit(async (values) => {
    setActionError(null);
    try {
      const inv = await apiFetch<Invitation>(`${base}/invitations`, {
        method: "POST",
        json: values,
      });
      setLastInvite(inv);
      reset({ email: "", role: values.role });
      refresh();
    } catch (e) {
      if (
        e instanceof ApiError &&
        (e.code === "already_member" || e.code === "invitation_exists")
      ) {
        setError("email", { message: e.message });
      } else
        setActionError(e instanceof ApiError ? e.message : "Request failed");
    }
  });

  const all = [...(members.data ?? [])].sort(byRoleThenName);
  const counts = new Map<string, number>();
  for (const m of all) counts.set(m.role, (counts.get(m.role) ?? 0) + 1);
  const needle = q.trim().toLowerCase();
  const shown = all.filter(
    (m) =>
      (!roleFilter || m.role === roleFilter) &&
      (!needle ||
        m.full_name.toLowerCase().includes(needle) ||
        m.email.toLowerCase().includes(needle)),
  );
  const pending = invitations.data ?? [];
  const cols = manage ? 4 : 3;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Members"
        meta={
          members.data
            ? `${all.length} ${all.length === 1 ? "person" : "people"} in ${active?.organization_name ?? "this organization"}${
                manage && pending.length > 0
                  ? ` · ${pending.length} invitation${pending.length === 1 ? "" : "s"} pending`
                  : ""
              }`
            : "Everyone with access to this organization, and what they can do."
        }
      />
      <ErrorText>{actionError}</ErrorText>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <div className="min-w-0 space-y-6">
          <TableCard
            toolbar={
              <>
                <SearchInput
                  label="Search members"
                  placeholder="Search name or email…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="w-full sm:w-60"
                />
                <div
                  role="group"
                  aria-label="Filter by role"
                  className="flex flex-wrap gap-1.5"
                >
                  {[["", all.length] as const, ...counts.entries()].map(
                    ([role, n]) => (
                      <button
                        key={role || "all"}
                        type="button"
                        aria-pressed={roleFilter === role}
                        onClick={() => setRoleFilter(role)}
                        className={`chip h-7 border px-2.5! transition-colors ${
                          roleFilter === role
                            ? "border-ink bg-accent text-accent-ink"
                            : "border-line-strong hover:border-ink"
                        }`}
                      >
                        {role
                          ? (ROLE_INFO[role]?.short ?? roleName(role))
                          : "All"}
                        <span className="opacity-60">{n}</span>
                      </button>
                    ),
                  )}
                </div>
              </>
            }
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Role</th>
                  <th className="hidden sm:table-cell">Joined</th>
                  {manage && (
                    <th className="text-right">
                      <span className="sr-only">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>
              {members.isLoading && <SkeletonRows cols={cols} rows={5} />}
              {members.error && (
                <TableMessage cols={cols}>
                  <span className="text-bad">{members.error.message}</span>
                </TableMessage>
              )}
              {members.data && shown.length === 0 && (
                <TableMessage cols={cols}>
                  No members match. Try a different search or role.
                </TableMessage>
              )}
              {shown.length > 0 && (
                <tbody>
                  {shown.map((m) => {
                    const me = m.user_id === user?.id;
                    const locked =
                      m.role === "club_owner" && myRole !== "club_owner";
                    return (
                      <tr key={m.id}>
                        <td>
                          <div className="flex items-center gap-3">
                            <PersonAvatar name={m.full_name} size="md" />
                            <div className="min-w-0">
                              <p className="flex flex-wrap items-center gap-1.5 font-semibold">
                                {m.full_name}
                                {me && (
                                  <span className="chip bg-volt/40 text-ink">
                                    You
                                  </span>
                                )}
                                {m.status !== "active" && (
                                  <span className="chip bg-warn-soft text-warn">
                                    {m.status}
                                  </span>
                                )}
                              </p>
                              <span className="sub truncate">{m.email}</span>
                            </div>
                          </div>
                        </td>
                        <td>
                          {manage && !locked && !me ? (
                            <select
                              aria-label={`Role for ${m.full_name}`}
                              value={m.role}
                              disabled={changeRole.isPending}
                              onChange={(e) => {
                                setActionError(null);
                                changeRole.mutate({
                                  id: m.id,
                                  role: e.target.value,
                                });
                              }}
                              className="field-input h-8! text-xs"
                            >
                              {assignable.map((r) => (
                                <option key={r} value={r}>
                                  {roleName(r)}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <RoleBadge role={m.role} />
                          )}
                        </td>
                        <td
                          className="hidden whitespace-nowrap sm:table-cell"
                          title={shortDate(m.joined_at)}
                        >
                          {shortDate(m.joined_at)}
                          <span className="sub">{timeAgo(m.joined_at)}</span>
                        </td>
                        {manage && (
                          <td className="text-right">
                            {!locked && !me && (
                              <button
                                type="button"
                                className="eyebrow rounded-[2px] px-2 py-1.5 text-bad transition-colors hover:bg-bad-soft"
                                onClick={() => {
                                  if (
                                    window.confirm(
                                      `Remove ${m.full_name} from this organization? They will lose access straight away.`,
                                    )
                                  ) {
                                    setActionError(null);
                                    remove.mutate(m.id);
                                  }
                                }}
                              >
                                Remove
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              )}
            </table>
          </TableCard>

          {manage && (
            <section aria-labelledby="pending-title" className="space-y-3">
              <h2 id="pending-title">
                Pending invitations{" "}
                <span className="font-mono text-sm opacity-50">
                  {pending.length}
                </span>
              </h2>
              <TableCard>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Invited</th>
                      <th>Role</th>
                      <th className="hidden sm:table-cell">Expires</th>
                      <th className="text-right">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  {invitations.isLoading && <SkeletonRows cols={4} rows={2} />}
                  {invitations.data && pending.length === 0 && (
                    <TableMessage cols={4}>
                      No pending invitations. Invite someone with the form.
                    </TableMessage>
                  )}
                  {pending.length > 0 && (
                    <tbody>
                      {pending.map((inv) => {
                        const expired = inv.status === "expired";
                        const exp = deadlineLabel(inv.expires_at);
                        return (
                          <tr key={inv.id}>
                            <td>
                              <div className="flex items-center gap-3">
                                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-dashed border-line-strong opacity-70">
                                  <MailIcon className="h-4 w-4" />
                                </span>
                                <div className="min-w-0">
                                  <p className="truncate font-medium">
                                    {inv.email}
                                  </p>
                                  <span className="sub">
                                    Sent {timeAgo(inv.created_at)}
                                  </span>
                                </div>
                              </div>
                            </td>
                            <td>
                              <RoleBadge role={inv.role} />
                            </td>
                            <td className="hidden whitespace-nowrap sm:table-cell">
                              {expired ? (
                                <span className="chip bg-warn-soft text-warn">
                                  Expired
                                </span>
                              ) : (
                                <span className="text-sm">
                                  {exp.text.replace("Due", "Expires")}
                                </span>
                              )}
                            </td>
                            <td className="text-right">
                              <button
                                type="button"
                                className="eyebrow rounded-[2px] px-2 py-1.5 transition-colors hover:bg-hover"
                                disabled={revoke.isPending}
                                onClick={() => {
                                  if (
                                    window.confirm(
                                      `Revoke the invitation for ${inv.email}? Their link will stop working.`,
                                    )
                                  )
                                    revoke.mutate(inv.id);
                                }}
                              >
                                Revoke
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  )}
                </table>
              </TableCard>
            </section>
          )}
        </div>

        <aside className="space-y-6 lg:sticky lg:top-20">
          {manage ? (
            <section aria-labelledby="invite-title" className="table-card">
              <div className="border-b border-line px-4 py-3">
                <h2 id="invite-title">Invite someone</h2>
                <p className="mt-1 text-xs opacity-60">
                  They sign up (or sign in) with this email and join with the
                  role you pick.
                </p>
              </div>
              <form
                method="post"
                onSubmit={invite}
                className="space-y-4 p-4"
                noValidate
              >
                <Field
                  label="Email"
                  type="email"
                  placeholder="name@club.com"
                  error={errors.email?.message}
                  {...register("email")}
                />
                <fieldset className="space-y-1.5">
                  <legend className="mb-1.5 text-sm font-medium">Role</legend>
                  {assignable.map((r) => (
                    <label
                      key={r}
                      className={`flex cursor-pointer gap-3 rounded-[3px] border p-2.5 transition-colors ${
                        chosenRole === r
                          ? "border-ink bg-volt/10"
                          : "border-line hover:border-line-strong"
                      }`}
                    >
                      <input
                        type="radio"
                        value={r}
                        className="mt-1"
                        {...register("role")}
                      />
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold">
                          {roleName(r)}
                        </span>
                        <span className="block text-xs opacity-65">
                          {ROLE_INFO[r]?.summary}
                        </span>
                      </span>
                    </label>
                  ))}
                </fieldset>
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full"
                >
                  <MailIcon className="h-4 w-4" />
                  {isSubmitting ? "Sending…" : "Send invitation"}
                </Button>
              </form>
              {lastInvite?.accept_url && (
                <div className="space-y-2 border-t border-line bg-volt/10 p-4 text-sm">
                  <p className="font-semibold">
                    Invitation created for {lastInvite.email}
                  </p>
                  <p className="text-xs opacity-75">
                    Email sending isn&apos;t connected yet, so share this link
                    with them yourself:
                  </p>
                  <CopyLink url={lastInvite.accept_url} />
                </div>
              )}
            </section>
          ) : (
            <section aria-labelledby="roles-title" className="table-card">
              <div className="border-b border-line px-4 py-3">
                <h2 id="roles-title">Roles</h2>
                <p className="mt-1 text-xs opacity-60">
                  What each person here can do. Ask an owner or administrator to
                  change roles.
                </p>
              </div>
              <ul className="divide-y divide-line-soft">
                {ORG_ROLES.map((r) => (
                  <li key={r} className="space-y-1 px-4 py-3">
                    <RoleBadge role={r} />
                    <p className="text-xs opacity-70">
                      {ROLE_INFO[r]?.summary}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
