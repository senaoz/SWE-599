import { cx } from "@/utils/cx";

// Cosine bands for Qwen3-Embedding scores; the cut-off itself is not calibrated yet.
function band(score: number) {
  if (score >= 0.7) return { fill: "bg-fg-success-primary", label: "Strong match" };
  if (score >= 0.55) return { fill: "bg-fg-brand-primary", label: "Good match" };
  return { fill: "bg-fg-quaternary", label: "Weak match" };
}

/** A match score as a small bar plus its percentage. */
export default function ScoreBar({ score, className }: { score: number; className?: string }) {
  const pct = Math.round(score * 100);
  const { fill, label } = band(score);
  return (
    <span className={cx("inline-flex items-center gap-1.5", className)} title={`${label} (cosine ${score.toFixed(2)})`}>
      <span className="h-1.5 w-10 overflow-hidden rounded-full bg-quaternary">
        <span className={cx("block h-full rounded-full", fill)} style={{ width: `${Math.max(pct, 4)}%` }} />
      </span>
      <span className="text-xs font-medium tabular-nums text-secondary">{pct}%</span>
    </span>
  );
}
