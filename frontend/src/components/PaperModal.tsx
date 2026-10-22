import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ModalOverlay,
  Modal,
  Dialog,
} from "@/components/application/modals/modal";
import { Badge } from "@/components/base/badges/badges";
import { LinkExternal01, XClose } from "@untitledui/icons";
import FeedbackButtons from "./FeedbackButtons";
import PublicationDate from "./PublicationDate";
import ScoreBar from "./ScoreBar";
import client from "../api/client";
import ResearcherModal from "./ResearcherModal";

interface MatchedBounPaper {
  title: string | null;
  score: number;
}
interface Researcher {
  researcher_id: string;
  display_name: string;
  score: number;
  matched_papers: MatchedBounPaper[];
}
interface PaperDetail {
  openalex_id: string;
  title: string | null;
  abstract: string | null;
  publication_date: string | null;
  source_institution_name: string | null;
  all_researchers: Researcher[];
}

interface Props {
  paperId: string;
  title: string | null;
  onClose: () => void;
}

export default function PaperModal({ paperId, title, onClose }: Props) {
  const [data, setData] = useState<PaperDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showFullAbstract, setShowFullAbstract] = useState(false);
  const [feedback, setFeedback] = useState<Record<string, boolean | null>>({});
  const [researcherModal, setResearcherModal] = useState<{
    name: string;
  } | null>(null);
  const [, setSearchParams] = useSearchParams();

  useEffect(() => {
    const shortId = paperId.replace("https://openalex.org/", "");
    setSearchParams(
      (p) => {
        p.set("paper", shortId);
        return p;
      },
      { replace: true },
    );
    return () =>
      setSearchParams(
        (p) => {
          p.delete("paper");
          return p;
        },
        { replace: true },
      );
  }, [paperId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    client
      .get<PaperDetail>(
        `/papers/${paperId.replace("https://openalex.org/", "")}`,
      )
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [paperId]);

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
          paper_openalex_id: paperId,
          researcher_id,
          is_relevant: next,
        })
        .catch(() =>
          setFeedback((f) => ({ ...f, [researcher_id]: prev ?? null })),
        );
    }
  };

  const abstract = data?.abstract ?? null;
  const longAbstract = !!abstract && abstract.length > 600;

  return (
    <>
      <ModalOverlay isOpen isDismissable onOpenChange={(open) => !open && onClose()}>
        <Modal className="max-w-2xl">
          <Dialog aria-label={data?.title ?? title ?? "Paper details"}>
            {() => (
              <div className="w-full max-w-2xl overflow-hidden rounded-2xl bg-primary shadow-xl ring-1 ring-primary">
                {/* Header */}
                <div className="flex items-start justify-between gap-4 border-b border-secondary px-6 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {data?.source_institution_name && (
                      <Badge type="color" color="blue" size="sm">
                        {data.source_institution_name}
                      </Badge>
                    )}
                    <PublicationDate date={data?.publication_date ?? null} />
                  </div>
                  <button
                    type="button"
                    aria-label="Close"
                    onClick={onClose}
                    className="shrink-0 cursor-pointer rounded-md p-1 text-fg-quaternary transition-colors hover:text-fg-secondary"
                  >
                    <XClose className="size-5" />
                  </button>
                </div>

                {/* Body */}
                <div className="max-h-[75vh] space-y-6 overflow-y-auto px-6 py-5">
                  <div className="space-y-3">
                    <h2 className="text-lg font-semibold leading-snug text-primary">
                      {data?.title ?? title ?? "(No title)"}
                    </h2>
                    <a
                      href={paperId}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-sm font-medium text-brand-secondary hover:underline"
                    >
                      Open in OpenAlex <LinkExternal01 className="size-3.5" />
                    </a>
                    {abstract && (
                      <div>
                        <p className={`text-sm leading-relaxed text-tertiary ${longAbstract && !showFullAbstract ? "line-clamp-6" : ""}`}>
                          {abstract}
                        </p>
                        {longAbstract && (
                          <button
                            type="button"
                            onClick={() => setShowFullAbstract((v) => !v)}
                            className="mt-1 text-sm font-medium text-brand-secondary hover:underline"
                          >
                            {showFullAbstract ? "Show less" : "Show more"}
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {loading && <p className="text-sm text-tertiary">Loading matches…</p>}

                  {!loading && data && (
                    <section>
                      <div className="mb-3 flex items-baseline justify-between gap-2">
                        <h3 className="text-sm font-semibold text-primary">Boğaziçi researchers on this topic</h3>
                        <span className="text-xs text-tertiary">{data.all_researchers.length} matched</span>
                      </div>

                      {data.all_researchers.length === 0 ? (
                        <p className="text-sm text-tertiary">No researcher matched yet.</p>
                      ) : (
                        <ol className="space-y-2">
                          {data.all_researchers.map((r, i) => (
                            <li key={r.researcher_id} className="rounded-xl p-3 ring-1 ring-secondary">
                              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                                <span className="w-5 text-xs font-medium tabular-nums text-quaternary">{i + 1}</span>
                                <button
                                  type="button"
                                  onClick={() => setResearcherModal({ name: r.display_name })}
                                  className="text-left text-sm font-semibold text-primary transition-colors hover:text-brand-secondary"
                                >
                                  {r.display_name}
                                </button>
                                <span className="ml-auto flex items-center gap-2">
                                  <ScoreBar score={r.score} />
                                  <FeedbackButtons
                                    value={feedback[r.researcher_id] ?? null}
                                    onChange={(v) => handleFeedback(r.researcher_id, v)}
                                    size="md"
                                  />
                                </span>
                              </div>
                              {r.matched_papers.length > 0 && (
                                <ul className="mt-2 space-y-1 border-l-2 border-secondary pl-3 ml-8">
                                  {r.matched_papers.map((mp, j) => (
                                    <li key={j} className="flex items-start gap-2 text-xs text-tertiary">
                                      <span className="w-8 shrink-0 tabular-nums text-quaternary">
                                        {Math.round(mp.score * 100)}%
                                      </span>
                                      <span>{mp.title}</span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </li>
                          ))}
                        </ol>
                      )}
                    </section>
                  )}
                </div>
              </div>
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>

      {researcherModal && (
        <ResearcherModal name={researcherModal.name} onClose={() => setResearcherModal(null)} />
      )}
    </>
  );
}
