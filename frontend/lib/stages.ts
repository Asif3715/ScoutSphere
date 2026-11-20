import { STAGES } from "@/lib/types";

/** Mirrors the backend `can_move` rules so the UI only offers legal moves. The server remains
 *  the authority and re-checks every move. */
export function canMove(current: string, target: string): boolean {
  if (current === target || current === "signed") return false;
  if (current === "rejected" || current === "archived")
    return target === "discovered";
  if (target === "rejected" || target === "archived") return true;
  if (target === "signed") return current === "negotiation";
  return true;
}

export const allowedStages = (current: string): string[] =>
  STAGES.filter((s) => canMove(current, s));
