"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { ClubForm } from "@/components/clubs/club-form";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import type { Club } from "@/lib/types";

export default function NewClubPage() {
  const { can } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  if (!can("clubs:manage")) {
    return (
      <p className="text-sm">You do not have permission to register clubs.</p>
    );
  }
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Register club</h1>
      <ClubForm
        submitLabel="Create club"
        onSubmit={async (payload) => {
          const club = await apiFetch<Club>("/clubs", {
            method: "POST",
            json: payload,
          });
          await queryClient.invalidateQueries({ queryKey: ["clubs"] });
          await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
          router.push(`/clubs/${club.id}`);
        }}
      />
    </div>
  );
}
