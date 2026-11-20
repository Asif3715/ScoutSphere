"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { RequirementForm } from "@/components/recruitment/requirement-form";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import type { Requirement } from "@/lib/types";

export default function NewRequirementPage() {
  const { can } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  if (!can("recruitment:manage"))
    return (
      <p className="text-sm">
        You do not have permission to create requirements.
      </p>
    );
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">New recruitment requirement</h1>
      <RequirementForm
        submitLabel="Create requirement"
        onSubmit={async (payload) => {
          const r = await apiFetch<Requirement>("/recruitment/requirements", {
            method: "POST",
            json: payload,
          });
          await qc.invalidateQueries({ queryKey: ["requirements"] });
          router.push(`/recruitment/${r.id}`);
        }}
      />
    </div>
  );
}
