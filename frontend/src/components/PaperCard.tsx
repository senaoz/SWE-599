import { useState } from "react";
import { Badge } from "@/components/base/badges/badges";
import ResearcherChip from "./ResearcherChip";
import PaperModal from "./PaperModal";
import client from "../api/client";

interface Researcher {
  researcher_id: string;
  display_name: string;
  score: number;
}

interface PaperCardProps {
  openalex_id: string;
  title: string | null;
  abstract: string | null;
  publication_date: string | null;
  source_institution_name: string | null;
  top_researchers: Researcher[];
  is_seen?: boolean;
}

export default function PaperCard({
  openalex_id, title, abstract, publication_date,
  source_institution_name, top_researchers, is_seen = false,
}: PaperCardProps) {
  const snippet = abstract ? abstract.slice(0, 280) + (abstract.length > 280 ? "…" : "") : null;
  const [feedback, setFeedback] = useState<Record<string, boolean | null>>({});
  const [seen, setSeen] = useState(is_seen);
  const [modalOpen, setModalOpen] = useState(false);

  const openModal = () => {
    setModalOpen(true);
    if (!seen) {
      setSeen(true);
      client.post(`/papers/${openalex_id.replace('https://openalex.org/', '')}/seen`).catch(() => {});
    }
  };

  const handleFeedback = async (researcher_id: string, is_relevant: boolean) => {
    const prev = feedback[researcher_id];
    const next = prev === is_relevant ? null : is_relevant;
    setFeedback(f => ({ ...f, [researcher_id]: next }));

    if (next !== null) {
      await client.post("/feedback", {
        paper_openalex_id: openalex_id,
        researcher_id,
        is_relevant: next,
      }).catch(() => {
        setFeedback(f => ({ ...f, [researcher_id]: prev ?? null }));
      });
    }
  };

  return (
    <div className={`rounded-xl bg-primary p-5 shadow-sm ring-1 mb-4 transition-colors ${seen ? "ring-secondary opacity-75" : "ring-primary"}`}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {source_institution_name && (
          <Badge type="color" color="blue" size="sm">
            {source_institution_name}
          </Badge>
        )}
        {publication_date && (
          <span className="text-xs text-tertiary">{publication_date}</span>
        )}
      </div>

      <button
        onClick={openModal}
        className="mb-2 block text-left text-md font-semibold text-primary leading-snug hover:text-brand-secondary transition-colors"
      >
        {title ?? "(No title)"}
      </button>

      {snippet && (
        <p className="mb-3 text-sm text-tertiary leading-relaxed">{snippet}</p>
      )}

      {top_researchers.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-xs text-quaternary">BOUN matches:</span>
          {top_researchers.map((r) => (
            <ResearcherChip
              key={r.researcher_id}
              id={r.researcher_id}
              name={r.display_name}
              score={r.score}
              feedback={feedback[r.researcher_id] ?? null}
              onFeedback={(isRelevant) => handleFeedback(r.researcher_id, isRelevant)}
            />
          ))}
        </div>
      )}

      {top_researchers.length === 0 && (
        <button
          onClick={openModal}
          className="mt-2 text-xs text-tertiary hover:text-brand-secondary transition-colors"
        >
          View details →
        </button>
      )}

      {modalOpen && (
        <PaperModal paperId={openalex_id} title={title} onClose={() => setModalOpen(false)} />
      )}
    </div>
  );
}
