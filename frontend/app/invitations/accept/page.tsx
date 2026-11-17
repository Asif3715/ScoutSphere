"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import type { Organization } from "@/lib/types";

type Preview = { organization_name: string; email: string; role: string };

function AcceptInvitation() {
  const token = useSearchParams().get("token") ?? "";
  const { user, loading, refreshProfile, logout } = useAuth();
  const router = useRouter();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    if (!token) return;
    apiFetch<Preview>("/invitations/preview", {
      method: "POST",
      json: { token },
      auth: false,
    })
      .then(setPreview)
      .catch((e) =>
        setError(
          e instanceof ApiError ? e.message : "Could not reach the server",
        ),
      );
  }, [token]);

  async function accept() {
    setAccepting(true);
    setError(null);
    try {
      const org = await apiFetch<Organization>("/invitations/accept", {
        method: "POST",
        json: { token },
      });
      await refreshProfile(org.id);
      router.replace("/dashboard");
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not accept the invitation",
      );
      setAccepting(false);
    }
  }

  const next = encodeURIComponent(`/invitations/accept?token=${token}`);
  const mismatch =
    !!user &&
    !!preview &&
    user.email.toLowerCase() !== preview.email.toLowerCase();

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-bold">ScoutSphere</h1>
      <ErrorText>
        {error ?? (token ? null : "This invitation link is incomplete.")}
      </ErrorText>
      {preview && (
        <>
          <p className="text-sm">
            You have been invited to join{" "}
            <strong>{preview.organization_name}</strong> as{" "}
            <strong>{preview.role.replace(/_/g, " ")}</strong>. The invitation
            is for {preview.email}.
          </p>
          {loading ? (
            <p aria-busy="true">Loading…</p>
          ) : !user ? (
            <div className="space-y-2 text-sm">
              <p>
                Sign in or create an account with {preview.email} to accept.
              </p>
              <div className="flex gap-2">
                <Link
                  className="rounded-md bg-teal-600 px-3 py-1.5 font-medium text-white"
                  href={`/login?next=${next}`}
                >
                  Sign in
                </Link>
                <Link
                  className="rounded-md border border-slate-300 px-3 py-1.5"
                  href={`/register?next=${next}`}
                >
                  Register
                </Link>
              </div>
            </div>
          ) : mismatch ? (
            <div className="space-y-2 text-sm">
              <ErrorText>
                You are signed in as {user.email}, but this invitation is for{" "}
                {preview.email}.
              </ErrorText>
              <Button
                variant="secondary"
                onClick={async () => {
                  await logout();
                  router.replace(`/login?next=${next}`);
                }}
              >
                Sign out and switch account
              </Button>
            </div>
          ) : (
            <Button onClick={accept} disabled={accepting}>
              {accepting ? "Joining…" : "Accept invitation"}
            </Button>
          )}
        </>
      )}
    </main>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={<main className="p-10">Loading…</main>}>
      <AcceptInvitation />
    </Suspense>
  );
}
