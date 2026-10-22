import { useState } from "react";
import { Tooltip, TooltipTrigger } from "@/components/base/tooltip/tooltip";
import FeedbackButtons from "./FeedbackButtons";
import ResearcherModal from "./ResearcherModal";
import ScoreBar from "./ScoreBar";

interface MatchedWork {
  title: string | null;
  score: number;
}

interface ResearcherChipProps {
  name: string;
  score: number;
  matchedPapers?: MatchedWork[];
  feedback?: boolean | null;
  onFeedback?: (isRelevant: boolean) => void;
}

/** One matched researcher under a paper: name and score, their matched works on hover, feedback. */
export default function ResearcherChip({ name, score, matchedPapers = [], feedback, onFeedback }: ResearcherChipProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const works = matchedPapers.filter((w) => w.title).slice(0, 3);

  return (
    <span
      className="inline-flex items-center gap-1 rounded-lg bg-primary py-0.5 pr-0.5 pl-2 ring-1 ring-secondary"
      onClick={(e) => e.stopPropagation()}
    >
      <Tooltip
        title={works.length ? "Matched through" : name}
        description={
          works.length ? (
            <span className="flex flex-col gap-1">
              {works.map((w, i) => (
                <span key={i}>
                  {Math.round(w.score * 100)}% · {w.title}
                </span>
              ))}
            </span>
          ) : undefined
        }
        placement="top"
      >
        <TooltipTrigger
          onPress={() => setModalOpen(true)}
          className="flex cursor-pointer items-center gap-2 rounded-md text-sm font-medium text-secondary hover:text-brand-secondary"
        >
          <span className="max-w-[12rem] truncate">{name}</span>
          <ScoreBar score={score} />
        </TooltipTrigger>
      </Tooltip>

      {onFeedback && <FeedbackButtons value={feedback ?? null} onChange={onFeedback} />}

      {modalOpen && <ResearcherModal name={name} onClose={() => setModalOpen(false)} />}
    </span>
  );
}
