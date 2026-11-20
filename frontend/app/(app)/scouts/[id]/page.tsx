"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ScoutForm } from "@/components/scouts/scout-form";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { ApiError, apiFetch } from "@/lib/http";
import { ROLE_LABELS, type Scout } from "@/lib/types";

export default function ScoutPage() {
  const { id } = useParams<{ id: string }>();
  const { activeOrgId, can } = useAuth();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    data: scout,
    error: loadError,
    isLoading,
  } = useQuery({
    queryKey: ["scout", activeOrgId, id],
    queryFn: () => apiFetch<Scout>(`/scouts/${id}`),
    enabled: !!activeOrgId,
  });

  if (isLoading) return <p aria-busy="true">Loading…</p>;
  if (loadError || !scout) {
    return (
      <div className="space-y-2">
        <ErrorText>{loadError?.message ?? "Scout not found"}</ErrorText>
        <Link href="/scouts" className="text-sm text-link underline">
          Back to scouts
        </Link>
      </div>
    );
  }
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["scout", activeOrgId, id] });
    qc.invalidateQueries({ queryKey: ["scouts"] });
  };

  async function setActive(active: boolean) {
    setError(null);
    try {
      await apiFetch(`/scouts/${id}`, {
        method: "PATCH",
        json: { is_active: active },
      });
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Request failed");
    }
  }

  return (
    <div className="space-y-4">
      <Link href="/scouts" className="text-sm text-link underline">
        ← Scouts
      </Link>
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            {scout.full_name}
            {!scout.is_active && (
              <span className="ml-2 rounded bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink/70">
                Inactive
              </span>
            )}
          </h1>
          <p className="text-sm opacity-70">
            {ROLE_LABELS[scout.org_role] ?? scout.org_role} · {scout.email}
            {scout.experience_years != null
              ? ` · ${scout.experience_years} years experience`
              : ""}
          </p>
        </div>
        {scout.can_edit && !editing && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Edit
            </Button>
            {can("scouts:manage") && (
              <Button
                variant="secondary"
                onClick={() => setActive(!scout.is_active)}
              >
                {scout.is_active ? "Deactivate" : "Reactivate"}
              </Button>
            )}
          </div>
        )}
      </header>
      <ErrorText>{error}</ErrorText>

      {editing ? (
        <ScoutForm
          scout={scout}
          submitLabel="Save changes"
          onSubmit={async (payload) => {
            await apiFetch(`/scouts/${id}`, { method: "PATCH", json: payload });
            refresh();
            setEditing(false);
          }}
        />
      ) : (
        <Card className="space-y-3 text-sm">
          {(
            [
              ["Positions", scout.positions],
              ["Age groups", scout.age_groups],
              ["Regions", scout.regions],
            ] as const
          ).map(([label, values]) => (
            <div key={label}>
              <p className="text-xs uppercase opacity-60">{label}</p>
              <p>{values.length ? values.join(", ") : "—"}</p>
            </div>
          ))}
          {scout.bio && <p className="whitespace-pre-wrap">{scout.bio}</p>}
          <p className="text-xs opacity-60">
            Assignments and report statistics will appear here once scouting
            assignments are available.
          </p>
        </Card>
      )}
    </div>
  );
}
