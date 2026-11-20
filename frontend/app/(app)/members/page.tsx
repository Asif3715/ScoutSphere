"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Field } from "@/components/auth/field";
import { Button, Card, Empty, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { inviteSchema, type InviteValues } from "@/lib/schemas";
import {
  ORG_ROLES,
  ROLE_LABELS,
  type Invitation,
  type Member,
} from "@/lib/types";

export default function MembersPage() {
  const { activeOrgId, user, can, memberships } = useAuth();
  const queryClient = useQueryClient();
  const manage = can("members:manage");
  const myRole = memberships.find(
    (m) => m.organization_id === activeOrgId,
  )?.role;
  // Only owners may grant or change owner access (the backend enforces this too).
  const assignable = ORG_ROLES.filter(
    (r) => r !== "club_owner" || myRole === "club_owner",
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastInvite, setLastInvite] = useState<Invitation | null>(null);

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
    formState: { errors, isSubmitting },
  } = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "scout" },
  });

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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Members</h1>
      <ErrorText>{actionError}</ErrorText>
      <ErrorText>{members.error?.message}</ErrorText>
      {members.isLoading && <p aria-busy="true">Loading…</p>}

      {members.data && (
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line text-xs uppercase opacity-60">
            <tr>
              <th className="py-2">Name</th>
              <th>Email</th>
              <th>Role</th>
              {manage && <th className="text-right">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {members.data.map((m) => {
              const isOwnerRow = m.role === "club_owner";
              const locked = isOwnerRow && myRole !== "club_owner";
              return (
                <tr key={m.id} className="border-b border-line-soft">
                  <td className="py-2">
                    {m.full_name}
                    {m.user_id === user?.id && (
                      <span className="ml-2 text-xs opacity-60">(you)</span>
                    )}
                  </td>
                  <td>{m.email}</td>
                  <td>
                    {manage && !locked ? (
                      <select
                        aria-label={`Role for ${m.full_name}`}
                        value={m.role}
                        disabled={changeRole.isPending}
                        onChange={(e) => {
                          setActionError(null);
                          changeRole.mutate({ id: m.id, role: e.target.value });
                        }}
                        className="rounded-[2px] border border-line-strong bg-transparent px-2 py-1"
                      >
                        {assignable.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </option>
                        ))}
                      </select>
                    ) : (
                      (ROLE_LABELS[m.role] ?? m.role)
                    )}
                  </td>
                  {manage && (
                    <td className="text-right">
                      {!locked && m.user_id !== user?.id && (
                        <Button
                          variant="danger"
                          onClick={() => {
                            if (
                              window.confirm(
                                `Remove ${m.full_name} from this organization?`,
                              )
                            ) {
                              setActionError(null);
                              remove.mutate(m.id);
                            }
                          }}
                        >
                          Remove
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {manage && (
        <>
          <Card className="max-w-xl space-y-3">
            <h2 className="font-semibold">Invite someone</h2>
            <form
              method="post"
              onSubmit={invite}
              className="space-y-3"
              noValidate
            >
              <Field
                label="Email"
                type="email"
                error={errors.email?.message}
                {...register("email")}
              />
              <div className="space-y-1">
                <label htmlFor="role" className="block text-sm font-medium">
                  Role
                </label>
                <select
                  id="role"
                  {...register("role")}
                  className="w-full rounded-[2px] border border-line-strong bg-transparent px-3 py-2 text-sm"
                >
                  {assignable.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Sending…" : "Send invitation"}
              </Button>
            </form>
            {lastInvite?.accept_url && (
              <div className="rounded-[2px] border-l-4 border-volt bg-surface-2 p-3 text-sm">
                <p className="font-medium">
                  Invitation created for {lastInvite.email}.
                </p>
                <p className="mt-1">
                  Email delivery is not connected yet. Share this link with them
                  (development only):
                </p>
                <input
                  readOnly
                  aria-label="Invitation link"
                  value={lastInvite.accept_url}
                  onFocus={(e) => e.currentTarget.select()}
                  className="mt-2 w-full rounded border border-line-strong bg-surface px-2 py-1 text-xs"
                />
              </div>
            )}
          </Card>

          <section className="space-y-2">
            <h2 className="font-semibold">Pending invitations</h2>
            {invitations.data && invitations.data.length === 0 && (
              <Empty>No pending invitations.</Empty>
            )}
            {invitations.data?.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center justify-between rounded-[2px] border border-line px-3 py-2 text-sm"
              >
                <span>
                  {inv.email} · {ROLE_LABELS[inv.role] ?? inv.role}
                  {inv.status === "expired" && (
                    <span className="ml-2 text-xs text-warn">expired</span>
                  )}
                </span>
                <Button
                  variant="secondary"
                  onClick={() => revoke.mutate(inv.id)}
                >
                  Revoke
                </Button>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
