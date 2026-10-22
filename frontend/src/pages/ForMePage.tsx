import { useState, useEffect, useRef } from "react";
import { ChevronLeft, ChevronRight, SearchLg, User01 } from "@untitledui/icons";
import { Avatar } from "@/components/base/avatar/avatar";
import { Button } from "@/components/base/buttons/button";
import { Toggle } from "@/components/base/toggle/toggle";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { cx } from "@/utils/cx";
import client from "../api/client";
import type { PapersResponse, ResearcherBrief } from "../api/types";
import { control, DATE_PRESETS, effectiveToDate, presetFromDate, SelectField, type DatePreset } from "../components/filters";
import PageHeader from "../components/PageHeader";
import PaperCard from "../components/PaperCard";
import ResearcherModal from "../components/ResearcherModal";
import { useMe } from "../hooks/useMe";

function initials(name: string): string {
  const parts = name.replace(/[^\p{L}\s]/gu, " ").split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** Shown until the account is linked to a Boğaziçi profile. */
function FindProfile() {
  const { claim } = useMe();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ResearcherBrief[]>([]);
  const [viewing, setViewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    timer.current = setTimeout(() => {
      client
        .get<{ researchers: ResearcherBrief[] }>("/researchers", { params: { q: query.trim(), limit: 8 } })
        .then((r) => setResults(r.data.researchers))
        .catch(() => setError("Search failed, try again."));
    }, 300);
  }, [query]);

  const pick = async (id: string) => {
    setError(null);
    try {
      await claim(id);
    } catch {
      setError("Could not link this profile.");
    }
  };

  return (
    <div className="rounded-xl bg-primary p-6 shadow-sm ring-1 ring-primary">
      <div className="mb-4 flex items-start gap-3">
        <span className="rounded-lg bg-brand-primary p-2 text-fg-brand-primary">
          <User01 className="size-5" />
        </span>
        <div>
          <h2 className="text-md font-semibold text-primary">Find your Boğaziçi profile</h2>
          <p className="mt-0.5 text-sm text-tertiary">
            Link your account to your researcher profile to see new papers close to your own work.
            Profiles come from OpenAlex; some people have two.
          </p>
        </div>
      </div>
      <div className="relative mb-3">
        <SearchLg className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-quaternary" />
        <input
          autoFocus
          type="text"
          placeholder="Your name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={cx(control, "h-10 w-full pl-9")}
        />
      </div>
      {error && <p className="mb-2 text-sm text-error-primary">{error}</p>}
      {results.length > 0 && (
        <ul className="divide-y divide-secondary overflow-hidden rounded-lg ring-1 ring-secondary">
          {results.map((r) => (
            <li key={r.id} className="flex items-center gap-3 px-3 py-2.5">
              <Avatar size="sm" initials={initials(r.display_name)} />
              <button
                type="button"
                onClick={() => setViewing(r.display_name)}
                className="min-w-0 flex-1 truncate text-left text-sm font-medium text-primary hover:text-brand-secondary"
              >
                {r.display_name}
                <span className="ml-2 text-xs font-normal text-tertiary">
                  {r.paper_count} {r.paper_count === 1 ? "work" : "works"}
                </span>
              </button>
              <Button color="secondary" size="sm" onClick={() => pick(r.id)}>
                This is me
              </Button>
            </li>
          ))}
        </ul>
      )}
      {query.trim().length >= 2 && results.length === 0 && !error && (
        <p className="text-sm text-tertiary">No researcher with that name.</p>
      )}
      {viewing && <ResearcherModal name={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}

export default function ForMePage() {
  const { me, unclaim } = useMe();
  const [data, setData] = useState<PapersResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preset, setPreset] = useState<DatePreset>("month");
  const [showFuture, setShowFuture] = useState(false);
  const researcher = me?.researcher ?? null;

  useEffect(() => {
    if (!researcher) return;
    setLoading(true);
    const params: Record<string, string | number> = { page, limit: 20 };
    const from = presetFromDate(preset);
    if (from) params.from_date = from;
    const to = effectiveToDate("", showFuture);
    if (to) params.to_date = to;
    client
      .get<PapersResponse>("/papers/for-me", { params })
      .then((r) => {
        setData(r.data);
        setError(null);
      })
      .catch(() => setError("Could not load your papers."))
      .finally(() => setLoading(false));
  }, [researcher, page, preset, showFuture]);

  if (!me) {
    return <p className="py-16 text-center text-sm text-tertiary">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <PageHeader
        title="For me"
        description={
          researcher ? (
            <>
              New papers close to the work of <span className="font-medium text-secondary">{researcher.display_name}</span>.{" "}
              <button type="button" onClick={unclaim} className="font-medium text-brand-secondary hover:underline">
                Not you?
              </button>
            </>
          ) : (
            "New papers close to your own work."
          )
        }
        actions={researcher && data && <span className="text-sm text-tertiary">{data.total} papers</span>}
      />

      {!researcher ? (
        <FindProfile />
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-3">
            <SelectField
              label="Published"
              value={preset}
              onChange={(v) => {
                setPage(1);
                setPreset(v as DatePreset);
              }}
              className="w-full sm:w-auto"
            >
              {DATE_PRESETS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </SelectField>
            <Toggle
              size="sm"
              label="Show future-dated papers"
              isSelected={showFuture}
              onChange={(v) => {
                setPage(1);
                setShowFuture(v);
              }}
            />
          </div>

          {error && <p className="py-8 text-center text-sm text-error-primary">{error}</p>}

          {data && data.total === 0 && !loading && !error && (
            <EmptyState size="md">
              <EmptyState.Header>
                <EmptyState.FeaturedIcon color="brand" icon={User01} />
              </EmptyState.Header>
              <EmptyState.Content>
                <EmptyState.Title>Nothing close to your work yet</EmptyState.Title>
                <EmptyState.Description>
                  New papers arrive from the institutions people follow. Try a longer period, or follow more
                  institutions.
                </EmptyState.Description>
              </EmptyState.Content>
              <EmptyState.Footer>
                <Button color="secondary" size="md" href="/institutions">
                  Institutions
                </Button>
              </EmptyState.Footer>
            </EmptyState>
          )}

          <div className={loading ? "pointer-events-none opacity-60" : ""}>
            {data?.papers.map((p) => <PaperCard key={p.openalex_id} paper={p} mode="forme" />)}
          </div>

          {data && data.pages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-3">
              <Button color="secondary" size="sm" iconLeading={ChevronLeft} isDisabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                Prev
              </Button>
              <span className="text-sm text-tertiary">
                Page {page} of {data.pages}
              </span>
              <Button color="secondary" size="sm" iconTrailing={ChevronRight} isDisabled={page === data.pages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
