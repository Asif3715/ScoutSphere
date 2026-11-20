"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PhotoEditor } from "@/components/players/photo-editor";
import { PlayerForm } from "@/components/players/player-form";
import { Card } from "@/components/ui/ui";
import { useAuth } from "@/lib/auth";
import { setFlash } from "@/lib/flash";
import { ApiError, apiFetch } from "@/lib/http";
import type { Crop } from "@/lib/media";
import type { Player } from "@/lib/types";

type PendingPhoto = { file: File; crop: Crop; preview: string };

export default function NewPlayerPage() {
  const { can } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  // The photo is chosen now but uploaded right after the player exists.
  const [photo, setPhoto] = useState<PendingPhoto | null>(null);

  if (!can("players:write"))
    return (
      <p className="text-sm">You do not have permission to add players.</p>
    );
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Add player</h1>
      <Card className="max-w-2xl space-y-3">
        <h2>Photo (optional)</h2>
        <PhotoEditor
          name="New player"
          current={photo?.preview ?? null}
          saveLabel="Use this photo"
          onSave={async (file, crop, preview) =>
            setPhoto({ file, crop, preview })
          }
          onRemove={async () => setPhoto(null)}
        />
      </Card>
      <PlayerForm
        submitLabel="Create player"
        onSubmit={async (payload, allowDuplicate) => {
          const p = await apiFetch<Player>("/players", {
            method: "POST",
            json: { ...payload, allow_duplicate: allowDuplicate },
          });
          if (photo) {
            const body = new FormData();
            body.append("file", photo.file);
            body.append("crop_x", String(photo.crop.x));
            body.append("crop_y", String(photo.crop.y));
            body.append("crop_size", String(photo.crop.size));
            try {
              await apiFetch(`/players/${p.id}/photo`, { method: "PUT", body });
            } catch (e) {
              setFlash({
                kind: "info",
                text: `${p.full_name} was created, but the photo could not be saved${
                  e instanceof ApiError ? `: ${e.message}` : ""
                }. You can add it below.`,
              });
            }
          }
          await queryClient.invalidateQueries({ queryKey: ["players"] });
          router.push(`/players/${p.id}`);
        }}
      />
    </div>
  );
}
