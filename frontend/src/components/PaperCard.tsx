import { Badge } from "@/components/base/badges/badges";
import ResearcherChip from "./ResearcherChip";

interface Researcher {
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
}

export default function PaperCard({
  openalex_id, title, abstract, publication_date,
  source_institution_name, top_researchers,
}: PaperCardProps) {
  const snippet = abstract ? abstract.slice(0, 280) + (abstract.length > 280 ? "…" : "") : null;

  return (
    <div className="rounded-xl bg-primary p-5 shadow-sm ring-1 ring-primary mb-4">
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

      <a
        href={openalex_id}
        target="_blank"
        rel="noreferrer"
        className="mb-2 block text-md font-semibold text-primary leading-snug hover:text-brand-secondary transition-colors"
      >
        {title ?? "(No title)"}
      </a>

      {snippet && (
        <p className="mb-3 text-sm text-tertiary leading-relaxed">{snippet}</p>
      )}

      {top_researchers.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-xs text-quaternary">BOUN matches:</span>
          {top_researchers.map((r) => (
            <ResearcherChip key={r.display_name} name={r.display_name} score={r.score} />
          ))}
        </div>
      )}
    </div>
  );
}
