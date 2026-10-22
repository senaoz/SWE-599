import { useState, useEffect, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { ModalOverlay, Modal, Dialog } from "@/components/application/modals/modal";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { LinkExternal01, Star01, XClose } from "@untitledui/icons";
import client from "../api/client";
import { useMe } from "../hooks/useMe";
import MatchLevel from "./MatchLevel";
import PublicationDate from "./PublicationDate";

interface MatchedPaper {
  openalex_id: string;
  title: string | null;
  publication_date: string | null;
  source_institution_name: string | null;
  score: number;
}
interface ResearcherMerged {
  display_name: string;
  ids: string[];
  openalex_urls: string[];
  total_papers: number;
  matched_papers: MatchedPaper[];
  total_matches: number;
  topics: string[];
  recent_works: { work_id: string; title: string | null; year: number | null }[];
  coauthors: { id: string; display_name: string; shared_works: number }[];
}

interface Props {
  name: string;
  onClose: () => void;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold text-primary">{title}</h3>
      {children}
    </section>
  );
}

export default function ResearcherModal({ name, onClose }: Props) {
  const [data, setData] = useState<ResearcherMerged | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [coauthor, setCoauthor] = useState<string | null>(null);
  const [favoriteError, setFavoriteError] = useState(false);
  const { me, addFavorite, removeFavorite } = useMe();
  const [, setSearchParams] = useSearchParams();

  useEffect(() => {
    setSearchParams((p) => {
      p.set("researcher", name);
      return p;
    }, { replace: true });
    return () =>
      setSearchParams((p) => {
        p.delete("researcher");
        return p;
      }, { replace: true });
  }, [name]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setLoading(true);
    client
      .get<ResearcherMerged>("/researchers/by-name", { params: { name } })
      .then((r) => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [name]);

  const isFavorite = !!data && !!me && me.favorites.some((f) => data.ids.includes(f.id));

  const toggleFavorite = async () => {
    if (!data) return;
    setFavoriteError(false);
    try {
      await (isFavorite ? removeFavorite(data.ids) : addFavorite(data.ids));
    } catch {
      setFavoriteError(true);
    }
  };

  return (
    <>
      <ModalOverlay isOpen isDismissable onOpenChange={(open) => !open && onClose()}>
        <Modal className="max-w-2xl">
          <Dialog aria-label={name}>
            {() => (
              <div className="w-full max-w-2xl overflow-hidden rounded-2xl bg-primary shadow-xl ring-1 ring-primary">
                <div className="flex items-start justify-between gap-4 border-b border-secondary px-6 py-4">
                  <div>
                    <h2 className="text-lg font-semibold text-primary">{name}</h2>
                    {data && (
                      <p className="mt-0.5 text-xs text-tertiary">
                        {data.total_papers} Boğaziçi works since 2020 · {data.total_matches} matched new papers
                      </p>
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
                  {loading && <p className="text-sm text-tertiary">Loading…</p>}
                  {error && <p className="text-sm text-error-primary">Could not load this researcher.</p>}

                  {data && (
                    <>
                      <div className="flex flex-wrap items-center gap-3">
                        <Button
                          color={isFavorite ? "primary" : "secondary"}
                          size="sm"
                          iconLeading={Star01}
                          onClick={toggleFavorite}
                        >
                          {isFavorite ? "Favourite" : "Add to favourites"}
                        </Button>
                        {data.openalex_urls.map((url, i) => (
                          <a
                            key={url}
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-sm font-medium text-brand-secondary hover:underline"
                          >
                            OpenAlex{data.openalex_urls.length > 1 ? ` ${i + 1}` : ""} <LinkExternal01 className="size-3.5" />
                          </a>
                        ))}
                        {favoriteError && <span className="text-xs text-error-primary">Could not update your favourites.</span>}
                      </div>

                      {data.topics.length > 0 && (
                        <Section title="Topics">
                          <div className="flex flex-wrap gap-1.5">
                            {data.topics.map((t) => (
                              <Badge key={t} type="color" color="gray" size="sm">
                                {t}
                              </Badge>
                            ))}
                          </div>
                        </Section>
                      )}

                      {data.recent_works.length > 0 && (
                        <Section title="Recent works">
                          <ul className="space-y-1 text-sm">
                            {data.recent_works.map((w) => (
                              <li key={w.work_id}>
                                <a href={w.work_id} target="_blank" rel="noreferrer" className="text-secondary hover:text-brand-secondary">
                                  {w.title ?? "(No title)"}
                                </a>
                                {w.year && <span className="text-quaternary"> ({w.year})</span>}
                              </li>
                            ))}
                          </ul>
                        </Section>
                      )}

                      {data.coauthors.length > 0 && (
                        <Section title="Boğaziçi co-authors">
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                            {data.coauthors.map((c) => (
                              <button
                                key={c.id}
                                type="button"
                                onClick={() => setCoauthor(c.display_name)}
                                className="text-secondary hover:text-brand-secondary"
                              >
                                {c.display_name} <span className="text-quaternary">· {c.shared_works}</span>
                              </button>
                            ))}
                          </div>
                        </Section>
                      )}

                      <Section title={`Matched new papers (${data.total_matches})`}>
                        {data.matched_papers.length === 0 ? (
                          <p className="text-sm text-tertiary">No matched papers yet.</p>
                        ) : (
                          <ul className="space-y-2">
                            {data.matched_papers.map((p) => (
                              <li key={p.openalex_id}>
                                <a
                                  href={`/explore?paper=${p.openalex_id.replace("https://openalex.org/", "")}`}
                                  className="block rounded-xl p-3 ring-1 ring-secondary transition-colors hover:bg-primary_hover"
                                >
                                  <div className="mb-1 flex flex-wrap items-center gap-2">
                                    {p.source_institution_name && (
                                      <span className="text-xs font-medium text-secondary">{p.source_institution_name}</span>
                                    )}
                                    <PublicationDate date={p.publication_date} />
                                    <MatchLevel score={p.score} className="ml-auto" />
                                  </div>
                                  <span className="text-sm font-medium text-primary">{p.title ?? "(No title)"}</span>
                                </a>
                              </li>
                            ))}
                          </ul>
                        )}
                      </Section>
                    </>
                  )}
                </div>
              </div>
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>

      {coauthor && <ResearcherModal name={coauthor} onClose={() => setCoauthor(null)} />}
    </>
  );
}
