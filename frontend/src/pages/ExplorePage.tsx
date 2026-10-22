import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen01, ChevronDown, ChevronLeft, ChevronRight, FilterLines, SearchLg, XClose } from "@untitledui/icons";
import client from "../api/client";
import PaperCard from "../components/PaperCard";
import type { PapersResponse } from "../api/types";
import { control, DATE_PRESETS, effectiveToDate, presetFromDate, SelectField, type DatePreset } from "../components/filters";
import PageHeader from "../components/PageHeader";
import PaperModal from "../components/PaperModal";
import ResearcherModal from "../components/ResearcherModal";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { Button } from "@/components/base/buttons/button";
import { Toggle } from "@/components/base/toggle/toggle";
import { cx } from "@/utils/cx";

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
  field: string;
  date_preset: DatePreset;
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
  field: "",
  date_preset: "any",
};

// Match levels; the bands follow MatchLevel.
const SCORE_OPTIONS = [
  { value: "0.3", label: "All matches" },
  { value: "0.55", label: "Likely or strong" },
  { value: "0.7", label: "Strong only" },
];




export default function ExplorePage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<PapersResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [fields, setFields] = useState<{ field: string; count: number }[]>([]);
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
      .catch((err) => console.error("Could not load institutions", err));
    client
      .get<{ field: string; count: number }[]>("/papers/fields")
      .then((r) => setFields(r.data))
      .catch((err) => console.error("Could not load fields", err));
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
    const fromDate = filters.from_date || presetFromDate(filters.date_preset);
    if (fromDate) params.from_date = fromDate;
    const toDate = effectiveToDate(filters.to_date, filters.show_future);
    if (toDate) params.to_date = toDate;
    if (filters.field) params.field = filters.field;
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
        title="Explore"
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
            label="Field"
            value={filters.field}
            onChange={(v) => setFilter("field", v)}
            className="w-full sm:w-auto sm:max-w-xs"
          >
            <option value="">All fields</option>
            {fields.map((f) => (
              <option key={f.field} value={f.field}>
                {f.field} ({f.count})
              </option>
            ))}
          </SelectField>

          <SelectField
            label="Published"
            value={filters.date_preset}
            onChange={(v) => setFilter("date_preset", v)}
            className="w-full sm:w-auto"
          >
            {DATE_PRESETS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </SelectField>

          <SelectField
            label="Match level"
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
          data?.papers.map((p) => <PaperCard key={p.openalex_id} paper={p} mode="explore" />)
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
