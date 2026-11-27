"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { PositionChip } from "@/components/players/position-chip";
import { PageHeader } from "@/components/ui/data-table";
import { PersonAvatar } from "@/components/ui/person";
import { Button, Card, ErrorText } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import { ApiError, apiFetch } from "@/lib/http";
import { tabKeys } from "@/lib/tabs";
import type { OrgClaim } from "@/lib/types";

const TONE = {
  approved: "bg-ok-soft text-ok",
  rejected: "bg-bad-soft text-bad",
  cancelled: "chip-outline",
  pending: "bg-warn-soft text-warn",
} as const;

function ClaimCard({ c }: { c: OrgClaim }) {
  const qc = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: (v: { decision: "approved" | "rejected"; note?: string }) =>
      apiFetch<OrgClaim>(`/player-claims/${c.id}/decision`, {
        method: "POST",
        json: v,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["claims"] });
      qc.invalidateQueries({ queryKey: ["players"] });
    },
  });

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <PersonAvatar name={c.requester_name} size="md" />
          <div>
            <p className="font-semibold">{c.requester_name}</p>
            <p className="text-sm opacity-70">{c.requester_email}</p>
          </div>
        </div>
        <span className={`chip ${TONE[c.status]}`}>{c.status}</span>
      </div>
      <p className="text-sm">
        says they are{" "}
        <Link
          href={`/players/${c.player_id}`}
          className="font-semibold text-link underline-offset-2 hover:underline"
        >
          {c.player_name}
        </Link>{" "}
        <span className="opacity-70">({c.player_age} years)</span>{" "}
        <PositionChip code={c.player_position} />
      </p>
      {c.message && (
        <p className="rounded-[2px] bg-surface-2 p-3 text-sm">“{c.message}”</p>
      )}
      <p className="text-xs opacity-60">
        Requested {timeAgo(c.created_at)}
        {c.decided_at &&
          ` · ${c.status} ${timeAgo(c.decided_at)}${c.decided_by_name ? ` by ${c.decided_by_name}` : ""}`}
        {c.decision_note && ` · “${c.decision_note}”`}
      </p>

      {c.status === "pending" && (
        <div className="space-y-3 border-t border-line pt-3">
          <p className="text-xs opacity-70">
            They proved they know this player&apos;s date of birth. Approve only
            if you recognise this person, for example from your squad list.
            Approving lets them edit their own profile and decide who can find
            them.
          </p>
          {rejecting && (
            <label className="flex flex-col gap-1">
              <span className="eyebrow opacity-70">
                Reason (they will see this)
              </span>
              <textarea
                rows={2}
                maxLength={500}
                className="field-input h-auto w-full py-2"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
          )}
          <ErrorText>
            {decide.error instanceof ApiError
              ? decide.error.message
              : decide.error && "Could not save the decision"}
          </ErrorText>
          <div className="flex flex-wrap gap-2">
            {!rejecting ? (
              <>
                <Button
                  onClick={() => decide.mutate({ decision: "approved" })}
                  disabled={decide.isPending}
                >
                  Approve
                </Button>
                <Button variant="danger" onClick={() => setRejecting(true)}>
                  Decline…
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="danger"
                  disabled={decide.isPending || !note.trim()}
                  onClick={() =>
                    decide.mutate({ decision: "rejected", note: note.trim() })
                  }
                >
                  Send decline
                </Button>
                <Button variant="secondary" onClick={() => setRejecting(false)}>
                  Back
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function ClaimsPage() {
  const { activeOrgId, can } = useAuth();
  const [tab, setTab] = useState<"pending" | "all">("pending");
  const claims = useQuery({
    queryKey: ["claims", activeOrgId, tab],
    queryFn: () =>
      apiFetch<OrgClaim[]>(
        tab === "pending"
          ? "/player-claims?status=pending"
          : "/player-claims?status=",
      ),
    enabled: !!activeOrgId && can("players:write"),
  });

  if (!can("players:write"))
    return (
      <Card>
        <p className="text-sm">You don&apos;t have access to claim requests.</p>
      </Card>
    );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Club"
        title="Player account requests"
        meta="Players ask to link their own account to the record you keep. Approving gives them control of their photo, details and visibility."
        actions={
          <Link href="/players" className="btn btn-secondary">
            ← Players
          </Link>
        }
      />
      <div
        role="tablist"
        onKeyDown={tabKeys}
        aria-label="Which requests"
        className="flex w-fit rounded-[2px] border border-line-strong p-0.5"
      >
        {(
          [
            ["pending", "Waiting"],
            ["all", "History"],
          ] as const
        ).map(([k, text]) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            tabIndex={tab === k ? 0 : -1}
            onClick={() => setTab(k)}
            className={`eyebrow rounded-[1px] px-3 py-2 transition-colors ${
              tab === k
                ? "bg-accent text-accent-ink"
                : "opacity-70 hover:opacity-100"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
      {claims.isLoading && (
        <p aria-busy="true" className="text-sm opacity-70">
          Loading…
        </p>
      )}
      <ErrorText>{claims.error?.message}</ErrorText>
      {claims.data?.length === 0 && (
        <Card>
          <p className="text-sm opacity-75">
            {tab === "pending"
              ? "Nothing waiting. When a player signs up and claims their profile, it will appear here."
              : "No requests yet."}
          </p>
        </Card>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {claims.data?.map((c) => (
          <ClaimCard key={c.id} c={c} />
        ))}
      </div>
    </div>
  );
}
