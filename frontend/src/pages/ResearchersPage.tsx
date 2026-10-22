import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { SearchLg, ChevronLeft, ChevronRight } from "@untitledui/icons";

function initials(name: string): string {
  const parts = name.replace(/[^\p{L}\s]/gu, " ").split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
import client from "../api/client";
import { Input } from "@/components/base/input/input";
import { Avatar } from "@/components/base/avatar/avatar";
import { Button } from "@/components/base/buttons/button";
import ResearcherModal from "../components/ResearcherModal";
import PageHeader from "../components/PageHeader";

interface Researcher {
  id: string;
  openalex_id: string;
  display_name: string;
  paper_count: number;
}

interface ResearchersResponse {
  researchers: Researcher[];
  total: number;
  page: number;
  pages: number;
}

export default function ResearchersPage() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [data, setData] = useState<ResearchersResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedName, setSelectedName] = useState<string | null>(() =>
    searchParams.get("researcher"),
  );
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = (q: string, p: number) => {
    setLoading(true);
    client
      .get<ResearchersResponse>("/researchers", {
        params: { q, page: p, limit: 20 },
      })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load("", 1);
  }, []);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setPage(1);
      load(query, 1);
    }, 300);
  }, [query]);

  const goTo = (p: number) => {
    setPage(p);
    load(query, p);
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <PageHeader
        title="Researchers"
        description="Boğaziçi University researchers with works since 2020."
        actions={data && <span className="text-sm text-tertiary">{data.total} researchers</span>}
      />

      <div className="mb-4">
        <Input
          icon={SearchLg}
          placeholder="Search by name…"
          value={query}
          onChange={(v) => setQuery(v)}
          isDisabled={false}
        />
      </div>

      <div className="relative">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-primary/60">
            <p className="text-sm text-tertiary">Loading…</p>
          </div>
        )}

        {data && data.researchers.length === 0 && !loading && (
          <p className="py-8 text-center text-sm text-tertiary">
            No researchers found.
          </p>
        )}

        {data &&
          data.researchers.length > 0 &&
          (() => {
            const grouped = data.researchers.reduce<
              Record<string, { paper_count: number }>
            >((acc, r) => {
              if (!acc[r.display_name])
                acc[r.display_name] = { paper_count: 0 };
              acc[r.display_name].paper_count += r.paper_count;
              return acc;
            }, {});
            const entries = Object.entries(grouped);
            return (
              <>
                <ul className="divide-y divide-secondary overflow-hidden rounded-xl bg-primary shadow-sm ring-1 ring-primary">
                  {entries.map(([name, info]) => (
                    <li key={name}>
                      <button
                        type="button"
                        onClick={() => setSelectedName(name)}
                        className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-primary_hover"
                      >
                        <Avatar size="sm" initials={initials(name)} />
                        <span className="min-w-0 flex-1 truncate text-sm font-medium text-primary group-hover:text-brand-secondary">
                          {name}
                        </span>
                        <span className="text-xs tabular-nums text-tertiary">
                          {info.paper_count} {info.paper_count === 1 ? "work" : "works"}
                        </span>
                        <ChevronRight className="size-4 text-fg-quaternary" />
                      </button>
                    </li>
                  ))}
                </ul>

                {data.pages > 1 && (
                  <div className="mt-6 flex items-center justify-center gap-3">
                    <Button
                      color="secondary"
                      size="sm"
                      iconLeading={ChevronLeft}
                      isDisabled={page <= 1}
                      onClick={() => goTo(page - 1)}
                    >
                      Prev
                    </Button>
                    <span className="text-sm text-tertiary">
                      Page {data.page} of {data.pages}
                    </span>
                    <Button
                      color="secondary"
                      size="sm"
                      iconTrailing={ChevronRight}
                      isDisabled={page >= data.pages}
                      onClick={() => goTo(page + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </>
            );
          })()}
      </div>

      {selectedName && (
        <ResearcherModal
          name={selectedName}
          onClose={() => setSelectedName(null)}
        />
      )}
    </div>
  );
}
