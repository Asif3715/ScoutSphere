"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { ScoutForm } from "@/components/scouts/scout-form";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import type { Member, Scout } from "@/lib/types";

export default function NewScoutPage() {
  const { activeOrgId, can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const manager = can("scouts:manage");
  const members = useQuery({
    queryKey: ["members", activeOrgId],
    queryFn: () => apiFetch<Member[]>(`/organizations/${activeOrgId}/members`),
    enabled: !!activeOrgId && manager && can("members:read"),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">
        {manager ? "Add scout profile" : "Create my scout profile"}
      </h1>
      <ScoutForm
        members={manager ? members.data : undefined}
        submitLabel="Create profile"
        onSubmit={async (payload) => {
          const s = await apiFetch<Scout>("/scouts", {
            method: "POST",
            json: payload,
          });
          await qc.invalidateQueries({ queryKey: ["scouts"] });
          router.push(`/scouts/${s.id}`);
        }}
      />
    </div>
  );
}
