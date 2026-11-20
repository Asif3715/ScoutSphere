"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { ReportEditor } from "@/components/reports/report-editor";
import { Card } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import { reportPayload } from "@/lib/schemas";
import type { AssignmentDetail, Player, ReportDetail } from "@/lib/types";

function NewReport() {
  const { activeOrgId, can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const params = useSearchParams();
  const assignmentId = params.get("assignment_id") ?? "";
  const playerId = params.get("player_id") ?? "";
  const matchId = params.get("match_id") ?? "";

  const assignment = useQuery({
    queryKey: ["assignment", activeOrgId, assignmentId],
    queryFn: () => apiFetch<AssignmentDetail>(`/assignments/${assignmentId}`),
    enabled: !!activeOrgId && !!assignmentId,
  });
  const player = useQuery({
    queryKey: ["player", activeOrgId, playerId],
    queryFn: () => apiFetch<Player>(`/players/${playerId}`),
    enabled: !!activeOrgId && !!playerId,
  });

  if (!can("reports:write"))
    return (
      <p className="text-sm">You do not have permission to write reports.</p>
    );

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">New scouting report</h1>
      {assignment.data && (
        <Card className="space-y-1 text-sm">
          <p>
            For assignment{" "}
            <Link
              href={`/assignments/${assignment.data.id}`}
              className="font-medium text-link underline"
            >
              {assignment.data.title}
            </Link>
          </p>
          {assignment.data.instructions && (
            <p className="whitespace-pre-wrap opacity-80">
              {assignment.data.instructions}
            </p>
          )}
          {assignment.data.criteria && (
            <p className="whitespace-pre-wrap opacity-80">
              Criteria: {assignment.data.criteria}
            </p>
          )}
        </Card>
      )}
      <ReportEditor
        key={`${player.data?.id ?? "none"}-${matchId}`}
        defaults={{ player_id: playerId, match_id: matchId }}
        playerName={player.data?.full_name}
        submitLabel="Save draft"
        onSubmit={async (values) => {
          const body = {
            ...reportPayload(values),
            player_id: values.player_id,
            match_id: matchId || values.match_id || null,
            assignment_id: assignmentId || null,
          };
          const r = await apiFetch<ReportDetail>("/scouting-reports", {
            method: "POST",
            json: body,
          });
          await qc.invalidateQueries({ queryKey: ["reports"] });
          await qc.invalidateQueries({ queryKey: ["assignment"] });
          router.push(`/reports/${r.id}`);
        }}
      />
    </div>
  );
}

export default function NewReportPage() {
  return (
    <Suspense fallback={<p aria-busy="true">Loading…</p>}>
      <NewReport />
    </Suspense>
  );
}
