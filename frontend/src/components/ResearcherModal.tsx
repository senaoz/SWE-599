import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ModalOverlay,
  Modal,
  Dialog,
} from "@/components/application/modals/modal";
import { Badge, BadgeWithIcon } from "@/components/base/badges/badges";
import { Link01 } from "@untitledui/icons";
import client from "../api/client";

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
}

interface Props {
  name: string;
  onClose: () => void;
}

export default function ResearcherModal({ name, onClose }: Props) {
  const [data, setData] = useState<ResearcherMerged | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [, setSearchParams] = useSearchParams();

  useEffect(() => {
    setSearchParams(
      (p) => {
        p.set("researcher", name);
        return p;
      },
      { replace: true },
    );
    return () =>
      setSearchParams(
        (p) => {
          p.delete("researcher");
          return p;
        },
        { replace: true },
      );
  }, [name]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    client
      .get<ResearcherMerged>("/researchers/by-name", { params: { name } })
      .then((r) => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [name]);

  return (
    <ModalOverlay isOpen onOpenChange={onClose}>
      <Modal className="max-w-2xl">
        <Dialog>
          {({ close }) => (
            <div className="w-full max-w-2xl rounded-2xl bg-primary ring-1 ring-primary shadow-xl overflow-hidden">
              {/* Header */}
              <div className="flex items-start justify-between gap-4 border-b border-secondary px-6 py-4">
                <div>
                  <h2 className="text-lg font-semibold text-primary">{name}</h2>
                  {data && (
                    <p className="text-xs text-tertiary mt-0.5">
                      {data.total_papers} BOUN papers · {data.total_matches}{" "}
                      recommendation matches
                    </p>
                  )}
                </div>
                <button
                  onClick={close}
                  className="shrink-0 text-quaternary hover:text-primary transition-colors text-lg leading-none cursor-pointer"
                >
                  ✕
                </button>
              </div>

              {/* Body */}
              <div className="max-h-[70vh] overflow-y-auto px-6 py-5 space-y-5">
                {loading && <p className="text-sm text-tertiary">Loading…</p>}
                {error && (
                  <p className="text-sm text-error-600">
                    Failed to load researcher data.
                  </p>
                )}

                {data && (
                  <>
                    {/* OpenAlex IDs */}
                    <div>
                      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-quaternary">
                        OpenAlex Profile
                        {data.openalex_urls.length > 1 ? "s" : ""}
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {data.openalex_urls.map((url, i) => (
                          <a
                            key={url}
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <BadgeWithIcon
                              iconLeading={Link01}
                              color="blue"
                              size="sm"
                            >
                              {data.ids[i]}
                            </BadgeWithIcon>
                          </a>
                        ))}
                      </div>
                    </div>

                    {/* Matched external papers */}
                    <div>
                      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-quaternary">
                        Matched External Papers ({data.total_matches})
                      </h3>

                      {data.matched_papers.length === 0 ? (
                        <p className="text-sm text-tertiary">
                          No matched papers yet.
                        </p>
                      ) : (
                        <ul className="space-y-2">
                          {data.matched_papers.map((p) => {
                            const pct = Math.round(p.score * 100);
                            const color =
                              pct >= 70
                                ? "success"
                                : pct >= 50
                                  ? "warning"
                                  : "gray";
                            return (
                              <li
                                key={p.openalex_id}
                                className="rounded-xl ring-1 ring-secondary p-3"
                              >
                                <div className="flex flex-wrap items-center gap-2 mb-1.5">
                                  {p.source_institution_name && (
                                    <Badge type="color" color="blue" size="sm">
                                      {p.source_institution_name}
                                    </Badge>
                                  )}
                                  {p.publication_date && (
                                    <span className="text-xs text-tertiary">
                                      {p.publication_date}
                                    </span>
                                  )}
                                  <Badge type="color" color={color} size="sm">
                                    {pct}% match
                                  </Badge>
                                </div>
                                <a
                                  href={p.openalex_id}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-sm font-medium text-primary hover:text-brand-secondary transition-colors"
                                >
                                  {p.title ?? "(No title)"}
                                </a>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
