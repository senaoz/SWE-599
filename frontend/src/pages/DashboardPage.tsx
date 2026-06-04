import { useState, useEffect, useRef } from "react";
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
  search: string;
  concept: string;
  institution_id: string;
  min_score: string;
  from_date: string;
  to_date: string;
  hide_unmatched: boolean;
}

const DEFAULT_FILTERS: Filters = {
  search: "",
  concept: "",
  institution_id: "",
  min_score: "0.3",
  from_date: "",
  to_date: "",
  hide_unmatched: false,
};

export default function DashboardPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<PapersResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [urlPaper, setUrlPaper] = useState(() => searchParams.get("paper"));
  const [urlResearcher, setUrlResearcher] = useState(() =>
    searchParams.get("researcher"),
  );
  const [searchInput, setSearchInput] = useState("");
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    client
      .get<Institution[]>("/institutions")
      .then((r) => setInstitutions(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number | boolean> = {
      page,
      limit: 20,
    };
    if (filters.search) params.search = filters.search;
    if (filters.concept) params.concept = filters.concept;
    if (filters.institution_id) params.institution_id = filters.institution_id;
    if (filters.min_score) params.min_score = filters.min_score;
    if (filters.from_date) params.from_date = filters.from_date;
    if (filters.to_date) params.to_date = filters.to_date;
    if (filters.hide_unmatched) params.include_unmatched = false;

    client
      .get<PapersResponse>("/papers", { params })
      .then((r) => {
        setData(r.data);
        setError(null);
      })
      .catch(() => setError("Failed to load papers"))
      .finally(() => setLoading(false));
  }, [page, filters]);

  const setFilter = (key: keyof Filters, value: string | boolean) => {
    setPage(1);
    setFilters((f) => ({ ...f, [key]: value }));
  };

  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    searchDebounce.current = setTimeout(() => {
      setPage(1);
      setFilters((f) => ({ ...f, search: value }));
    }, 400);
  };

  const resetFilters = () => {
    setPage(1);
    setSearchInput("");
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
        <div className="flex items-center gap-3">
          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="text-xs text-brand-secondary hover:underline"
            >
              Reset filters
            </button>
          )}
          <span className="text-sm text-tertiary">
            {data?.total ?? 0} papers
          </span>
        </div>
      </div>

      {/* Search bar */}
      <div className="mb-3 relative">
        <input
          type="text"
          placeholder="Search papers by title or abstract…"
          value={searchInput}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="w-full rounded-xl bg-primary px-4 py-2.5 pl-10 text-sm text-primary placeholder:text-quaternary focus:outline-none focus:ring-2 focus:ring-brand-solid ring-1 ring-primary"
        />
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-quaternary"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"
          />
        </svg>
        {searchInput && (
          <button
            onClick={() => handleSearchChange("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-quaternary hover:text-secondary"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
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
              min={DEFAULT_FILTERS.min_score}
              max="1"
              step="0.05"
              value={filters.min_score}
              onChange={(e) => {
                const v = parseFloat(e.target.value);
                const minScore = parseFloat(DEFAULT_FILTERS.min_score);
                if (!isNaN(v) && v >= minScore)
                  setFilter("min_score", e.target.value);
              }}
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

        <div className="mt-3 flex items-end justify-between gap-3">
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-medium text-tertiary">
              Topic / Tag
            </label>
            <input
              type="text"
              placeholder="e.g. Machine Learning"
              value={filters.concept}
              onChange={(e) => setFilter("concept", e.target.value)}
              className="rounded-lg border border-secondary bg-primary px-2 py-1.5 text-sm text-primary placeholder:text-quaternary focus:outline-none focus:ring-2 focus:ring-brand-solid"
            />
          </div>
          <label className="flex cursor-pointer items-center gap-2 select-none h-[38px]">
            <div
              onClick={() =>
                setFilter("hide_unmatched", !filters.hide_unmatched)
              }
              className={`relative h-5 w-9 rounded-full transition-colors ${
                filters.hide_unmatched ? "bg-brand-solid" : "bg-secondary"
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  filters.hide_unmatched ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </div>
            <span className="text-xs text-secondary">
              Hide unmatched papers
            </span>
          </label>
        </div>
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
        <ResearcherModal
          name={urlResearcher}
          onClose={() => setUrlResearcher(null)}
        />
      )}
    </div>
  );
}
