import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, ArrowLeft } from "@untitledui/icons";
import client from "../api/client";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";

interface MatchedPaper {
  openalex_id: string;
  title: string | null;
  publication_date: string | null;
  source_institution_name: string | null;
  score: number;
}

interface ResearcherDetail {
  id: string;
  openalex_id: string;
  display_name: string;
  paper_count: number;
  matched_papers: MatchedPaper[];
  total_matches: number;
  page: number;
  pages: number;
}

export default function ResearcherDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ResearcherDetail | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    client.get<ResearcherDetail>(`/researchers/${id}`, { params: { page, limit: 20 } })
      .then(r => { setData(r.data); setError(null); })
      .catch(() => setError("Researcher not found"))
      .finally(() => setLoading(false));
  }, [id, page]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-sm text-tertiary">Loading…</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <p className="text-sm text-error-600">{error ?? "Not found"}</p>
        <Link to="/researchers" className="mt-2 inline-flex items-center gap-1 text-sm text-brand-secondary hover:underline">
          <ArrowLeft className="size-4" /> Back to researchers
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <Link
        to="/researchers"
        className="mb-6 inline-flex items-center gap-1 text-sm text-tertiary hover:text-primary transition-colors"
      >
        <ArrowLeft className="size-4" /> Researchers
      </Link>

      <div className="mb-6 rounded-xl bg-primary p-5 ring-1 ring-primary shadow-sm">
        <a
          href={data.openalex_id}
          target="_blank"
          rel="noreferrer"
          className="text-xl font-semibold text-primary hover:text-brand-secondary transition-colors"
        >
          {data.display_name}
        </a>
        <div className="mt-2 flex gap-4 text-sm text-tertiary">
          <span>{data.paper_count} BOUN papers</span>
          <span>{data.total_matches} recommendation matches</span>
        </div>
      </div>

      <h2 className="mb-4 text-sm font-semibold text-secondary">
        Matched external papers
        {data.total_matches > 0 && (
          <span className="ml-2 font-normal text-tertiary">({data.total_matches})</span>
        )}
      </h2>

      {data.matched_papers.length === 0 ? (
        <p className="py-8 text-center text-sm text-tertiary">No matched papers yet.</p>
      ) : (
        <ul className="space-y-3">
          {data.matched_papers.map(p => {
            const pct = Math.round(p.score * 100);
            const color = pct >= 70 ? "success" : pct >= 50 ? "warning" : "gray";
            return (
              <li key={p.openalex_id} className="rounded-xl bg-primary p-4 ring-1 ring-primary shadow-sm">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  {p.source_institution_name && (
                    <Badge type="color" color="blue" size="sm">{p.source_institution_name}</Badge>
                  )}
                  {p.publication_date && (
                    <span className="text-xs text-tertiary">{p.publication_date}</span>
                  )}
                  <Badge type="color" color={color} size="sm">{pct}% match</Badge>
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

      {data.pages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button
            color="secondary"
            size="sm"
            iconLeading={ChevronLeft}
            isDisabled={page === 1}
            onClick={() => setPage(p => p - 1)}
          >
            Prev
          </Button>
          <span className="text-sm text-tertiary">Page {page} of {data.pages}</span>
          <Button
            color="secondary"
            size="sm"
            iconTrailing={ChevronRight}
            isDisabled={page === data.pages}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
