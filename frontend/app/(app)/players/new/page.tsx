"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { PlayerForm } from "@/components/players/player-form";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/http";
import type { Player } from "@/lib/types";

export default function NewPlayerPage() {
  const { can } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  if (!can("players:write"))
    return (
      <p className="text-sm">You do not have permission to add players.</p>
    );
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Add player</h1>
      <PlayerForm
        submitLabel="Create player"
        onSubmit={async (payload, allowDuplicate) => {
          const p = await apiFetch<Player>("/players", {
            method: "POST",
            json: { ...payload, allow_duplicate: allowDuplicate },
          });
          await queryClient.invalidateQueries({ queryKey: ["players"] });
          router.push(`/players/${p.id}`);
        }}
      />
    </div>
  );
}
