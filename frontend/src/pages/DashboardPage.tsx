import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen01, ChevronLeft, ChevronRight } from "@untitledui/icons";
import client from "../api/client";
import PaperCard from "../components/PaperCard";
import PaperModal from "../components/PaperModal";
import ResearcherModal from "../components/ResearcherModal";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { Button } from "@/components/base/buttons/button";

interface Researcher {
  researcher_id: string;
  display_name: string;
  score: number;
}
interface Paper {
  openalex_id: string;
  title: string | null;
  abstract: string | null;
  publication_date: string | null;
  source_institution_name: string | null;
  top_researchers: Researcher[];
}
interface PapersResponse {
  papers: Paper[];
  total: number;
  page: number;
  pages: number;
}
interface Institution {
  institution_openalex_id: string;
  institution_name: string;
}

interface Filters {
  institution_id: string;
  min_score: string;
  from_date: string;
  to_date: string;
}

const DEFAULT_FILTERS: Filters = {
  institution_id: "",
  min_score: "0.3",
  from_date: "",
  to_date: "",
};

export default function DashboardPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<PapersResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [urlPaper, setUrlPaper] = useState(() => searchParams.get('paper'));
  const [urlResearcher, setUrlResearcher] = useState(() => searchParams.get('researcher'));

  useEffect(() => {
    client
      .get<Institution[]>("/institutions")
      .then((r) => setInstitutions(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, limit: 20 };
    if (filters.institution_id) params.institution_id = filters.institution_id;
    if (filters.min_score) params.min_score = filters.min_score;
    if (filters.from_date) params.from_date = filters.from_date;
    if (filters.to_date) params.to_date = filters.to_date;

    client
      .get<PapersResponse>("/papers", { params })
      .then((r) => {
        setData(r.data);
        setError(null);
        console.log(r.data);
      })
      .catch(() => setError("Failed to load papers"))
      .finally(() => setLoading(false));
  }, [page, filters]);

  const setFilter = (key: keyof Filters, value: string) => {
    setPage(1);
    setFilters((f) => ({ ...f, [key]: value }));
  };

  const resetFilters = () => {
    setPage(1);
    setFilters(DEFAULT_FILTERS);
  };

  const hasActiveFilters = Object.entries(filters).some(
    ([k, v]) => v !== DEFAULT_FILTERS[k as keyof Filters],
  );

  if (loading && !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-sm text-tertiary">Loading papers…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <EmptyState size="md">
          <EmptyState.Header>
            <EmptyState.FeaturedIcon color="error" icon={BookOpen01} />
          </EmptyState.Header>
          <EmptyState.Content>
            <EmptyState.Title>Failed to load papers</EmptyState.Title>
            <EmptyState.Description>{error}</EmptyState.Description>
          </EmptyState.Content>
          <EmptyState.Footer>
            <Button color="primary" size="md" onClick={() => setPage(1)}>
              Try again
            </Button>
          </EmptyState.Footer>
        </EmptyState>
      </div>
    );
  }

  if (!data || (data.total === 0 && !hasActiveFilters)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4">
        <EmptyState size="lg">
          <EmptyState.Header>
            <EmptyState.FeaturedIcon color="brand" icon={BookOpen01} />
          </EmptyState.Header>
          <EmptyState.Content>
            <EmptyState.Title>No papers yet</EmptyState.Title>
            <EmptyState.Description>
              Follow some institutions to start receiving paper recommendations.
            </EmptyState.Description>
          </EmptyState.Content>
          <EmptyState.Footer>
            <Button color="primary" size="md" href="/institutions">
              Browse institutions
            </Button>
          </EmptyState.Footer>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-primary">Latest Papers</h1>
        <span className="text-sm text-tertiary">{data?.total ?? 0} papers</span>
      </div>

      {/* Filter bar */}
      <div className="mb-6 rounded-xl bg-primary p-4 ring-1 ring-primary shadow-sm">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-tertiary">
              Institution
            </label>
            <select
              value={filters.institution_id}
              onChange={(e) => setFilter("institution_id", e.target.value)}
              className="rounded-lg border border-secondary bg-primary px-2 py-1.5 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-brand-solid"
            >
              <option value="">All</option>
              {institutions.map((i) => (
                <option
                  key={i.institution_openalex_id}
                  value={i.institution_openalex_id}
                >
                  {i.institution_name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-tertiary">
              Min score
            </label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={filters.min_score}
              onChange={(e) => setFilter("min_score", e.target.value)}
              className="rounded-lg border border-secondary bg-primary px-2 py-1.5 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-brand-solid"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-tertiary">
              From date
            </label>
            <input
              type="date"
              value={filters.from_date}
              onChange={(e) => setFilter("from_date", e.target.value)}
              className="rounded-lg border border-secondary bg-primary px-2 py-1.5 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-brand-solid"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-tertiary">To date</label>
            <input
              type="date"
              value={filters.to_date}
              onChange={(e) => setFilter("to_date", e.target.value)}
              className="rounded-lg border border-secondary bg-primary px-2 py-1.5 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-brand-solid"
            />
          </div>
        </div>

        {hasActiveFilters && (
          <div className="mt-3 flex justify-end">
            <button
              onClick={resetFilters}
              className="text-xs text-brand-secondary hover:underline"
            >
              Reset filters
            </button>
          </div>
        )}
      </div>

      <div className={loading ? "opacity-60 pointer-events-none" : ""}>
        {data && data.papers.length === 0 ? (
          <p className="py-8 text-center text-sm text-tertiary">
            No papers match the current filters.
          </p>
        ) : (
          data?.papers.map((p) => <PaperCard key={p.openalex_id} {...p} />)
        )}
      </div>

      {data && data.pages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button
            color="secondary"
            size="sm"
            iconLeading={ChevronLeft}
            isDisabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Prev
          </Button>
          <span className="text-sm text-tertiary">
            Page {page} of {data.pages}
          </span>
          <Button
            color="secondary"
            size="sm"
            iconTrailing={ChevronRight}
            isDisabled={page === data.pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {urlPaper && (
        <PaperModal
          paperId={`https://openalex.org/${urlPaper}`}
          title={null}
          onClose={() => setUrlPaper(null)}
        />
      )}
      {urlResearcher && !urlPaper && (
        <ResearcherModal name={urlResearcher} onClose={() => setUrlResearcher(null)} />
      )}
    </div>
  );
}
