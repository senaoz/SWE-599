import { useState, useEffect, useRef, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen01, ChevronDown, ChevronLeft, ChevronRight, FilterLines, SearchLg, XClose } from "@untitledui/icons";
import client from "../api/client";
import PaperCard from "../components/PaperCard";
import PageHeader from "../components/PageHeader";
import PaperModal from "../components/PaperModal";
import ResearcherModal from "../components/ResearcherModal";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { Button } from "@/components/base/buttons/button";
import { Toggle } from "@/components/base/toggle/toggle";
import { cx } from "@/utils/cx";

interface Researcher {
  researcher_id: string;
  display_name: string;
  score: number;
  matched_papers?: { title: string | null; score: number }[];
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
  show_future: boolean;
}

const DEFAULT_FILTERS: Filters = {
  search: "",
  concept: "",
  institution_id: "",
  min_score: "0.3",
  from_date: "",
  to_date: "",
  hide_unmatched: false,
  show_future: false,
};

// Match-score options; the bands follow ScoreBar.
const SCORE_OPTIONS = [
  { value: "0.3", label: "All matches" },
  { value: "0.55", label: "Good or better (55%+)" },
  { value: "0.7", label: "Strong only (70%+)" },
];

const control =
  "h-9 rounded-lg bg-primary px-3 text-sm text-primary shadow-xs ring-1 ring-primary ring-inset placeholder:text-placeholder focus:outline-none focus:ring-2 focus:ring-brand";

/** A native select (keyboard and mobile pickers for free) with our own arrow, spaced from the edge. */
function SelectField({
  label,
  value,
  onChange,
  className,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={cx("relative inline-flex", className)}>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cx(control, "w-full cursor-pointer appearance-none truncate pr-10")}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-fg-quaternary" />
    </span>
  );
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

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
  const [moreFilters, setMoreFilters] = useState(false);
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
    // Future-dated papers (often a journal's issue date) are hidden unless asked for.
    const today = todayIso();
    const toDate = filters.show_future ? filters.to_date : filters.to_date && filters.to_date < today ? filters.to_date : today;
    if (toDate) params.to_date = toDate;
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
      <PageHeader
        title="Latest papers"
        description="New papers from the institutions you follow, with the Boğaziçi researchers who work on each topic."
        actions={
          <>
            {hasActiveFilters && (
              <button
                onClick={resetFilters}
                className="text-sm font-medium text-brand-secondary hover:underline"
              >
                Reset filters
              </button>
            )}
            <span className="text-sm text-tertiary">{data?.total ?? 0} papers</span>
          </>
        }
      />

      {/* Search and filters */}
      <div className="mb-6 space-y-3">
        <div className="relative">
          <SearchLg className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-quaternary" />
          <input
            type="text"
            placeholder="Search papers by title or abstract…"
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            className={cx(control, "h-10 w-full pl-9", searchInput && "pr-9")}
          />
          {searchInput && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => handleSearchChange("")}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-fg-quaternary hover:text-fg-secondary"
            >
              <XClose className="size-4" />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <SelectField
            label="Institution"
            value={filters.institution_id}
            onChange={(v) => setFilter("institution_id", v)}
            className="w-full sm:w-auto sm:max-w-xs"
          >
            <option value="">All institutions</option>
            {institutions.map((i) => (
              <option key={i.institution_openalex_id} value={i.institution_openalex_id}>
                {i.institution_name}
              </option>
            ))}
          </SelectField>

          <SelectField
            label="Match score"
            value={filters.min_score}
            onChange={(v) => setFilter("min_score", v)}
            className="w-full sm:w-auto"
          >
            {SCORE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </SelectField>

          <Button
            color="secondary"
            size="sm"
            iconLeading={FilterLines}
            iconTrailing={ChevronDown}
            onClick={() => setMoreFilters((v) => !v)}
            aria-expanded={moreFilters}
            className={cx("h-9", moreFilters && "[&_svg:last-child]:rotate-180")}
          >
            More filters
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <Toggle
            size="sm"
            label="Show future-dated papers"
            isSelected={filters.show_future}
            onChange={(v) => setFilter("show_future", v)}
          />
          <Toggle
            size="sm"
            label="Hide papers without matches"
            isSelected={filters.hide_unmatched}
            onChange={(v) => setFilter("hide_unmatched", v)}
          />
        </div>

        {moreFilters && (
          <div className="grid grid-cols-1 gap-3 rounded-xl bg-primary p-4 ring-1 ring-secondary sm:grid-cols-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-secondary">Published from</span>
              <input
                type="date"
                value={filters.from_date}
                onChange={(e) => setFilter("from_date", e.target.value)}
                className={control}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-secondary">Published until</span>
              <input
                type="date"
                value={filters.to_date}
                onChange={(e) => setFilter("to_date", e.target.value)}
                className={control}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-secondary">Topic or tag</span>
              <input
                type="text"
                placeholder="e.g. Machine learning"
                value={filters.concept}
                onChange={(e) => setFilter("concept", e.target.value)}
                className={control}
              />
            </label>
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
        <ResearcherModal
          name={urlResearcher}
          onClose={() => setUrlResearcher(null)}
        />
      )}
    </div>
  );
}
