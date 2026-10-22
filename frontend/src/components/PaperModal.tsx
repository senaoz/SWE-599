import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { ModalOverlay, Modal, Dialog } from "@/components/application/modals/modal";
import { Badge } from "@/components/base/badges/badges";
import { LinkExternal01, XClose } from "@untitledui/icons";
import client from "../api/client";
import type { PaperDetail } from "../api/types";
import MatchLevel from "./MatchLevel";
import PaperMeta from "./PaperMeta";
import ResearcherModal from "./ResearcherModal";
import VerdictControl from "./VerdictControl";

interface Props {
  paperId: string;
  title: string | null;
  onClose: () => void;
}

function ExternalLink({ href, children }: { href: string; children: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-sm font-medium text-brand-secondary hover:underline"
    >
      {children} <LinkExternal01 className="size-3.5" />
    </a>
  );
}

export default function PaperModal({ paperId, title, onClose }: Props) {
  const [data, setData] = useState<PaperDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showFullAbstract, setShowFullAbstract] = useState(false);
  const [researcherName, setResearcherName] = useState<string | null>(null);
  const [, setSearchParams] = useSearchParams();
  const shortId = paperId.replace("https://openalex.org/", "");

  useEffect(() => {
    setSearchParams((p) => {
      p.set("paper", shortId);
      return p;
    }, { replace: true });
    return () =>
      setSearchParams((p) => {
        p.delete("paper");
        return p;
      }, { replace: true });
  }, [shortId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    client
      .get<PaperDetail>(`/papers/${shortId}`)
      .then((r) => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [shortId]);

  const abstract = data?.abstract ?? null;
  const longAbstract = !!abstract && abstract.length > 600;

  return (
    <>
      <ModalOverlay isOpen isDismissable onOpenChange={(open) => !open && onClose()}>
        <Modal className="max-w-2xl">
          <Dialog aria-label={data?.title ?? title ?? "Paper details"}>
            {() => (
              <div className="w-full max-w-2xl overflow-hidden rounded-2xl bg-primary shadow-xl ring-1 ring-primary">
                <div className="flex items-start justify-between gap-4 border-b border-secondary px-6 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {data && (
                      <PaperMeta
                        institution={data.source_institution_name}
                        date={data.publication_date}
                        type={data.type}
                        hasAbstract={!!data.abstract}
                      />
                    )}
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

                <div className="max-h-[75vh] space-y-6 overflow-y-auto px-6 py-5">
                  <div className="space-y-3">
                    <div>
                      <h2 className="text-lg font-semibold leading-snug text-primary">
                        {data?.title ?? title ?? "(No title)"}
                      </h2>
                      {data?.field && <p className="mt-1 text-sm text-tertiary">{data.field}</p>}
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1">
                      {data?.doi && <ExternalLink href={`https://doi.org/${data.doi.replace(/^https?:\/\/doi\.org\//, "")}`}>DOI</ExternalLink>}
                      {data?.oa_url && <ExternalLink href={data.oa_url}>Open-access copy</ExternalLink>}
                      <ExternalLink href={paperId}>OpenAlex</ExternalLink>
                    </div>
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
                  {error && <p className="text-sm text-error-primary">Could not load this paper.</p>}

                  {data && (
                    <section>
                      <div className="mb-3 flex items-baseline justify-between gap-2">
                        <h3 className="text-sm font-semibold text-primary">Boğaziçi researchers on this topic</h3>
                        <span className="text-xs text-tertiary">{data.all_researchers.length} matched</span>
                      </div>
                      {data.all_researchers.length === 0 ? (
                        <p className="text-sm text-tertiary">No researcher matched yet.</p>
                      ) : (
                        <ol className="space-y-2">
                          {data.all_researchers.map((r) => (
                            <li key={r.researcher_id} className="space-y-2.5 rounded-xl p-3 ring-1 ring-secondary">
                              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                                <span className="w-5 text-xs font-medium tabular-nums text-quaternary">{r.rank}</span>
                                <button
                                  type="button"
                                  onClick={() => setResearcherName(r.display_name)}
                                  className="text-left text-sm font-semibold text-primary transition-colors hover:text-brand-secondary"
                                >
                                  {r.display_name}
                                </button>
                                <MatchLevel score={r.score} className="ml-auto" />
                              </div>
                              {r.matched_papers.length > 0 && (
                                <ul className="ml-8 space-y-1 border-l-2 border-secondary pl-3">
                                  {r.matched_papers.map((w) => (
                                    <li key={w.work_id} className="text-xs text-tertiary">
                                      <span className="text-secondary">{w.title}</span>
                                      {w.year && <span className="text-quaternary"> ({w.year})</span>}
                                      {w.large_collaboration && (
                                        <span className="ml-1.5 align-middle">
                                          <Badge type="color" color="gray" size="sm">Collaboration</Badge>
                                        </span>
                                      )}
                                    </li>
                                  ))}
                                </ul>
                              )}
                              <div className="ml-8">
                                <VerdictControl paperId={paperId} researcherId={r.researcher_id} initial={r.my_verdict} />
                              </div>
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

      {researcherName && <ResearcherModal name={researcherName} onClose={() => setResearcherName(null)} />}
    </>
  );
}
