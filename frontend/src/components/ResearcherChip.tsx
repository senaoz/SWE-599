import { BadgeWithDot } from "@/components/base/badges/badges";

interface ResearcherChipProps {
  name: string;
  score: number;
}

export default function ResearcherChip({ name, score }: ResearcherChipProps) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "success" : pct >= 50 ? "warning" : "gray";

  return (
    <BadgeWithDot color={color} size="sm">
      {name} · {pct}%
    </BadgeWithDot>
  );
}
