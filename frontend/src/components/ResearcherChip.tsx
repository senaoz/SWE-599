import { useState } from "react";
import { BadgeWithDot } from "@/components/base/badges/badges";
import ResearcherModal from "./ResearcherModal";

interface ResearcherChipProps {
  id: string;
  name: string;
  score: number;
  feedback?: boolean | null;
  onFeedback?: (isRelevant: boolean) => void;
}

export default function ResearcherChip({ id: _id, name, score, feedback, onFeedback }: ResearcherChipProps) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "success" : pct >= 50 ? "warning" : "gray";
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="flex items-center gap-1">
      <button onClick={() => setModalOpen(true)} className="focus:outline-none">
        <BadgeWithDot color={color} size="sm">
          {name} · {pct}%
        </BadgeWithDot>
      </button>

      {onFeedback && (
        <div className="flex gap-0.5">
          <button
            title="Relevant"
            onClick={() => onFeedback(true)}
            className={`rounded p-0.5 transition-colors ${feedback === true ? "text-success-600" : "text-quaternary hover:text-success-600"}`}
          >
            <svg className="size-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
              <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
            </svg>
          </button>
          <button
            title="Not relevant"
            onClick={() => onFeedback(false)}
            className={`rounded p-0.5 transition-colors ${feedback === false ? "text-error-600" : "text-quaternary hover:text-error-600"}`}
          >
            <svg className="size-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
              <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
            </svg>
          </button>
        </div>
      )}

      {modalOpen && <ResearcherModal name={name} onClose={() => setModalOpen(false)} />}
    </div>
  );
}
