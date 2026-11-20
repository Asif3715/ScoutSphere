import { POSITION_GROUPS } from "@/lib/types";

const GROUP_TONE: Record<string, string> = {
  goalkeeper: "bg-warn",
  defender: "bg-info",
  midfielder: "bg-ok",
  forward: "bg-bad",
};

export function positionGroup(code: string | null | undefined) {
  if (!code) return null;
  return (
    Object.entries(POSITION_GROUPS).find(([, codes]) =>
      codes.includes(code),
    )?.[0] ?? null
  );
}

/** Position code with a colour tick for its line (keeper, defence, midfield, attack). */
export function PositionChip({ code }: { code: string | null | undefined }) {
  if (!code) return <span className="opacity-40">—</span>;
  const group = positionGroup(code);
  return (
    <span className="chip chip-outline" title={group ?? undefined}>
      <span
        aria-hidden="true"
        className={`h-2 w-1 rounded-[1px] ${group ? GROUP_TONE[group] : "bg-line-strong"}`}
      />
      {code}
    </span>
  );
}
