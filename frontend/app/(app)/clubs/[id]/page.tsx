"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ClubForm } from "@/components/clubs/club-form";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import type { Club } from "@/lib/types";

export default function ClubDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId, can } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: club,
    error,
    isLoading,
  } = useQuery({
    queryKey: ["club", activeOrgId, id],
    queryFn: () => apiFetch<Club>(`/clubs/${id}`),
    enabled: !!activeOrgId,
  });

  if (isLoading) return <p aria-busy="true">Loading…</p>;
  if (error || !club) {
    return (
      <div className="space-y-2">
        <ErrorText>{error?.message ?? "Club not found"}</ErrorText>
        <Link href="/clubs" className="text-sm text-link underline">
          Back to clubs
        </Link>
      </div>
    );
  }

  const editable = can("clubs:manage") && !club.is_reference;

  async function archive() {
    if (
      !window.confirm(
        `Archive ${club!.name}? It will no longer appear in your club list.`,
      )
    )
      return;
    setActionError(null);
    try {
      await apiFetch(`/clubs/${id}`, { method: "DELETE" });
      await queryClient.invalidateQueries({ queryKey: ["clubs"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      router.replace("/clubs");
    } catch (e) {
      setActionError(
        e instanceof ApiError ? e.message : "Could not archive the club",
      );
    }
  }

  return (
    <div className="space-y-4">
      <Link href="/clubs" className="text-sm text-link underline">
        ← Clubs
      </Link>
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{club.name}</h1>
          <p className="text-sm opacity-70">
            {[club.city, club.country].filter(Boolean).join(", ") ||
              "Location not set"}
            {club.is_reference && " · Reference club (read-only)"}
          </p>
        </div>
        {editable && !editing && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button variant="danger" onClick={archive}>
              Archive
            </Button>
          </div>
        )}
      </header>
      <ErrorText>{actionError}</ErrorText>

      {editing ? (
        <ClubForm
          club={club}
          submitLabel="Save changes"
          onSubmit={async (payload) => {
            await apiFetch<Club>(`/clubs/${id}`, {
              method: "PATCH",
              json: payload,
            });
            await queryClient.invalidateQueries({
              queryKey: ["club", activeOrgId, id],
            });
            await queryClient.invalidateQueries({ queryKey: ["clubs"] });
            setEditing(false);
          }}
        />
      ) : (
        <Card>
          <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
            {(
              [
                ["Short name", club.short_name],
                ["Founded", club.founded_year],
                ["Website", club.website],
                ["Contact email", club.contact_email],
                ["Contact phone", club.contact_phone],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="opacity-60">{label}</dt>
                <dd>{value ?? "—"}</dd>
              </div>
            ))}
          </dl>
          {club.description && (
            <p className="mt-4 whitespace-pre-wrap text-sm">
              {club.description}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
