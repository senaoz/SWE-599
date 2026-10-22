import { cx } from "@/utils/cx";

// The score is an uncalibrated cosine (docs/MATCHING_DESIGN.md), so it is shown as a level, not a percentage.
export function matchLevel(score: number) {
  if (score >= 0.7) return { label: "Strong", dot: "bg-fg-success-primary" };
  if (score >= 0.55) return { label: "Likely", dot: "bg-fg-brand-primary" };
  return { label: "Weak", dot: "bg-fg-quaternary" };
}

/** A match level with a coloured dot; the exact cosine is in the tooltip. */
export default function MatchLevel({ score, className }: { score: number; className?: string }) {
  const { label, dot } = matchLevel(score);
  return (
    <span
      className={cx("inline-flex items-center gap-1.5 text-xs font-medium text-tertiary", className)}
      title={`${label} match (cosine ${score.toFixed(2)}; not a probability)`}
    >
      <span className={cx("size-1.5 rounded-full", dot)} />
      {label}
    </span>
  );
}
