import { Badge } from "@/components/base/badges/badges";
import PublicationDate from "./PublicationDate";

const TYPE_LABELS: Record<string, string> = {
  dataset: "Dataset",
  software: "Software",
  preprint: "Preprint",
  review: "Review",
  "book-chapter": "Book chapter",
};

interface PaperMetaProps {
  institution: string | null;
  date: string | null;
  type: string | null;
  hasAbstract: boolean;
}

/** The line above a paper title: institution, state badges, date. */
export default function PaperMeta({ institution, date, type, hasAbstract }: PaperMetaProps) {
  const typeLabel = type ? TYPE_LABELS[type] : undefined;
  return (
    <>
      {institution && <span className="text-xs font-medium text-secondary">{institution}</span>}
      {typeLabel && (
        <Badge type="color" color="gray" size="sm">
          {typeLabel}
        </Badge>
      )}
      {!hasAbstract && (
        <span title="No abstract in OpenAlex: matched from the title only, so matches are less reliable.">
          <Badge type="color" color="gray" size="sm">
            Title only
          </Badge>
        </span>
      )}
      <PublicationDate date={date} />
    </>
  );
}
