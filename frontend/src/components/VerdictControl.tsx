import { useState } from "react";
import { cx } from "@/utils/cx";
import client from "../api/client";
import type { Verdict, VerdictReason } from "../api/types";

const VERDICTS: { value: Verdict; label: string }[] = [
  { value: "yes", label: "Yes" },
  { value: "partly", label: "Partly" },
  { value: "no", label: "No" },
];

const REASONS: { value: VerdictReason; label: string }[] = [
  { value: "different_field", label: "Different field" },
  { value: "too_general", label: "Too general" },
  { value: "collaboration_only", label: "Only via a collaboration" },
  { value: "same_author", label: "Same author" },
];

interface VerdictControlProps {
  paperId: string;
  researcherId: string;
  initial: Verdict | null;
  /** The question; For me asks about the user's own work. */
  question?: string;
}

/** Asks whether a researcher works on a paper's topic. The answer is the app's only relevance signal. */
export default function VerdictControl({
  paperId,
  researcherId,
  initial,
  question = "Works on this topic?",
}: VerdictControlProps) {
  const [verdict, setVerdict] = useState<Verdict | null>(initial);
  const [reason, setReason] = useState<VerdictReason | null>(null);
  const [error, setError] = useState(false);

  const send = async (next: Verdict | null, nextReason: VerdictReason | null) => {
    const prev = [verdict, reason] as const;
    setVerdict(next);
    setReason(nextReason);
    setError(false);
    try {
      await client.post("/feedback", {
        paper_openalex_id: paperId,
        researcher_id: researcherId,
        verdict: next,
        reason: nextReason,
      });
    } catch {
      setVerdict(prev[0]);
      setReason(prev[1]);
      setError(true);
    }
  };

  return (
    <div className="flex flex-col gap-1.5" onClick={(e) => e.stopPropagation()}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-tertiary">{question}</span>
        <div role="group" aria-label={question} className="inline-flex overflow-hidden rounded-lg ring-1 ring-primary">
          {VERDICTS.map((v) => (
            <button
              key={v.value}
              type="button"
              aria-pressed={verdict === v.value}
              onClick={() => send(verdict === v.value ? null : v.value, null)}
              className={cx(
                "cursor-pointer px-2.5 py-1 text-xs font-medium transition-colors not-first:border-l not-first:border-primary",
                verdict === v.value ? "bg-brand-solid text-white" : "bg-primary text-secondary hover:bg-primary_hover",
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
        {error && <span className="text-xs text-error-primary">Not saved, try again</span>}
      </div>
      {(verdict === "no" || verdict === "partly") && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-quaternary">Why? (optional)</span>
          {REASONS.map((r) => (
            <button
              key={r.value}
              type="button"
              aria-pressed={reason === r.value}
              onClick={() => send(verdict, reason === r.value ? null : r.value)}
              className={cx(
                "cursor-pointer rounded-full px-2 py-0.5 text-xs ring-1 transition-colors",
                reason === r.value
                  ? "bg-brand-primary text-brand-secondary ring-brand"
                  : "text-tertiary ring-secondary hover:text-secondary",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
