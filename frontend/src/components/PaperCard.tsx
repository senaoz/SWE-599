import { useState } from "react";
import { Eye } from "@untitledui/icons";
import { Badge, BadgeWithIcon } from "@/components/base/badges/badges";
import ResearcherChip from "./ResearcherChip";
import PublicationDate from "./PublicationDate";
import PaperModal from "./PaperModal";
import client from "../api/client";

interface Researcher {
  researcher_id: string;
  display_name: string;
  score: number;
  matched_papers?: { title: string | null; score: number }[];
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
  openalex_id,
  title,
  abstract,
  publication_date,
  source_institution_name,
  top_researchers,
  is_seen = false,
}: PaperCardProps) {
  const snippet = abstract
    ? abstract.slice(0, 280) + (abstract.length > 280 ? "…" : "")
    : null;
  const [feedback, setFeedback] = useState<Record<string, boolean | null>>({});
  const [seen, setSeen] = useState(is_seen);
  const [modalOpen, setModalOpen] = useState(false);

  const openModal = () => {
    setModalOpen(true);
    if (!seen) {
      setSeen(true);
      client
        .post(
          `/papers/${openalex_id.replace("https://openalex.org/", "")}/seen`,
        )
        .catch(() => {});
    }
  };

  const handleFeedback = async (
    researcher_id: string,
    is_relevant: boolean,
  ) => {
    const prev = feedback[researcher_id];
    const next = prev === is_relevant ? null : is_relevant;
    setFeedback((f) => ({ ...f, [researcher_id]: next }));

    if (next !== null) {
      await client
        .post("/feedback", {
          paper_openalex_id: openalex_id,
          researcher_id,
          is_relevant: next,
        })
        .catch(() => {
          setFeedback((f) => ({ ...f, [researcher_id]: prev ?? null }));
        });
    }
  };

  return (
    <>
    <div
      className={`mb-4 cursor-pointer rounded-xl p-5 ring-1 transition ${
        seen
          ? "bg-secondary_alt ring-secondary"
          : "bg-primary shadow-sm ring-primary hover:shadow-md"
      }`}
      onClick={openModal}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {source_institution_name && (
          <Badge type="color" color="blue" size="sm">
            {source_institution_name}
          </Badge>
        )}
        <PublicationDate date={publication_date} />
        {seen && (
          <BadgeWithIcon type="color" color="gray" size="sm" iconLeading={Eye} className="ml-auto">
            Viewed
          </BadgeWithIcon>
        )}
      </div>

      <button
        onClick={openModal}
        className={`mb-2 block text-left text-md leading-snug transition-colors hover:text-brand-secondary ${
          seen ? "font-medium text-tertiary" : "font-semibold text-primary"
        }`}
      >
        {title ?? "(No title)"}
      </button>

      {snippet && (
        <p className="mb-3 line-clamp-4 text-sm leading-relaxed text-tertiary sm:line-clamp-none">{snippet}</p>
      )}

      {top_researchers.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-secondary pt-3">
          <span className="text-xs font-medium text-tertiary">Boğaziçi researchers on this topic</span>
          <div className="flex flex-wrap items-center gap-1.5">
          {top_researchers.map((r) => (
            <ResearcherChip
              key={r.researcher_id}
              name={r.display_name}
              score={r.score}
              matchedPapers={r.matched_papers}
              feedback={feedback[r.researcher_id] ?? null}
              onFeedback={(isRelevant) =>
                handleFeedback(r.researcher_id, isRelevant)
              }
            />
          ))}
          </div>
        </div>
      )}

      {top_researchers.length === 0 && (
        <p className="border-t border-secondary pt-3 text-xs text-tertiary">
          No Boğaziçi researcher matched yet.
        </p>
      )}

    </div>

      {modalOpen && (
        <PaperModal
          paperId={openalex_id}
          title={title}
          onClose={() => setModalOpen(false)}
        />
      )}
    </>
  );
}
