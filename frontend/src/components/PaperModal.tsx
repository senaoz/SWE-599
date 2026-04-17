import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { ModalOverlay, Modal, Dialog } from "@/components/application/modals/modal";
import { Badge } from "@/components/base/badges/badges";
import client from "../api/client";
import ResearcherModal from "./ResearcherModal";

interface MatchedBounPaper { title: string | null; score: number; }
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
  const [feedback, setFeedback] = useState<Record<string, boolean | null>>({});
  const [researcherModal, setResearcherModal] = useState<{ name: string } | null>(null);
  const [, setSearchParams] = useSearchParams();

  useEffect(() => {
    const shortId = paperId.replace('https://openalex.org/', '');
    setSearchParams(p => { p.set('paper', shortId); return p; }, { replace: true });
    return () => setSearchParams(p => { p.delete('paper'); return p; }, { replace: true });
  }, [paperId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    client.get<PaperDetail>(`/papers/${paperId.replace('https://openalex.org/', '')}`)
      .then(r => setData(r.data))
      .finally(() => setLoading(false));
  }, [paperId]);

  const handleFeedback = async (researcher_id: string, is_relevant: boolean) => {
    const prev = feedback[researcher_id];
    const next = prev === is_relevant ? null : is_relevant;
    setFeedback(f => ({ ...f, [researcher_id]: next }));
    if (next !== null) {
      await client.post("/feedback", { paper_openalex_id: paperId, researcher_id, is_relevant: next })
        .catch(() => setFeedback(f => ({ ...f, [researcher_id]: prev ?? null })));
    }
  };

  return (
    <>
      <ModalOverlay isOpen onOpenChange={onClose}>
        <Modal className="max-w-2xl">
          <Dialog>
            {({ close }) => (
              <div className="w-full max-w-2xl rounded-2xl bg-primary ring-1 ring-primary shadow-xl overflow-hidden">
                {/* Header */}
                <div className="flex items-start justify-between gap-4 border-b border-secondary px-6 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {data?.source_institution_name && (
                      <Badge type="color" color="blue" size="sm">{data.source_institution_name}</Badge>
                    )}
                    {data?.publication_date && (
                      <span className="text-xs text-tertiary">{data.publication_date}</span>
                    )}
                  </div>
                  <button onClick={close} className="shrink-0 text-quaternary hover:text-primary transition-colors text-lg leading-none cursor-pointer">✕</button>
                </div>

                {/* Body */}
                <div className="max-h-[70vh] overflow-y-auto px-6 py-5 space-y-5">
                  <div>
                    <a
                      href={paperId}
                      target="_blank"
                      rel="noreferrer"
                      className="text-lg font-semibold text-primary hover:text-brand-secondary transition-colors leading-snug"
                    >
                      {title ?? "(No title)"}
                    </a>
                    {data?.abstract && (
                      <p className="mt-2 text-sm text-tertiary leading-relaxed">{data.abstract}</p>
                    )}
                  </div>

                  {loading && <p className="text-sm text-tertiary">Loading matches…</p>}

                  {!loading && data && (
                    <div>
                      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-quaternary">
                        BOUN Researcher Matches ({data.all_researchers.length})
                      </h3>

                      {data.all_researchers.length === 0 ? (
                        <p className="text-sm text-tertiary">No matches found yet.</p>
                      ) : (
                        <ul className="space-y-3">
                          {data.all_researchers.map(r => {
                            const pct = Math.round(r.score * 100);
                            const color = pct >= 70 ? "success" : pct >= 50 ? "warning" : "gray";
                            const fb = feedback[r.researcher_id] ?? null;
                            return (
                              <li key={r.researcher_id} className="rounded-xl ring-1 ring-secondary p-3 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                  <button
                                    onClick={() => setResearcherModal({ name: r.display_name })}
                                    className="text-sm font-medium text-primary hover:text-brand-secondary transition-colors text-left"
                                  >
                                    {r.display_name}
                                  </button>
                                  <div className="flex items-center gap-2 shrink-0">
                                    <Badge type="color" color={color} size="sm">{pct}%</Badge>
                                    <div className="flex gap-0.5">
                                      <button
                                        title="Relevant"
                                        onClick={() => handleFeedback(r.researcher_id, true)}
                                        className={`rounded p-1 transition-colors ${fb === true ? "text-success-600" : "text-quaternary hover:text-success-600"}`}
                                      >
                                        <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
                                          <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
                                        </svg>
                                      </button>
                                      <button
                                        title="Not relevant"
                                        onClick={() => handleFeedback(r.researcher_id, false)}
                                        className={`rounded p-1 transition-colors ${fb === false ? "text-error-600" : "text-quaternary hover:text-error-600"}`}
                                      >
                                        <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                          <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
                                          <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
                                        </svg>
                                      </button>
                                    </div>
                                  </div>
                                </div>
                                {r.matched_papers.length > 0 && (
                                  <ul className="space-y-1 pl-2 border-l-2 border-secondary">
                                    {r.matched_papers.map((mp, i) => (
                                      <li key={i} className="text-xs text-tertiary flex items-start gap-2">
                                        <span className="shrink-0 text-quaternary">{Math.round(mp.score * 100)}%</span>
                                        <span>{mp.title}</span>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
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
