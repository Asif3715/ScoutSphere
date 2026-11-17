import type { MatchSummary } from "@/lib/types";

export function ScoreCell({
  m,
}: {
  m: Pick<MatchSummary, "home_score" | "away_score">;
}) {
  if (m.home_score == null) return <span className="opacity-50">–</span>;
  return (
    <strong>
      {m.home_score} – {m.away_score}
    </strong>
  );
}
