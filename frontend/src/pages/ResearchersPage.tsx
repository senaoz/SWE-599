import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { SearchLg, User01, ChevronLeft, ChevronRight } from "@untitledui/icons";
import client from "../api/client";
import { Input } from "@/components/base/input/input";
import ResearcherModal from "../components/ResearcherModal";

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
  const [selectedName, setSelectedName] = useState<string | null>(() => searchParams.get('researcher'));
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = (q: string, p: number) => {
    setLoading(true);
    client
      .get<ResearchersResponse>("/researchers", { params: { q, page: p, limit: 20 } })
      .then(r => setData(r.data))
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
      <div className="mb-6 flex items-center gap-2">
        <User01 className="size-5 text-tertiary" />
        <h1 className="text-xl font-semibold text-primary">BOUN Researchers</h1>
        {data && (
          <span className="ml-auto text-sm text-tertiary">{data.total} researchers</span>
        )}
      </div>

      <div className="mb-4">
        <Input
          icon={SearchLg}
          placeholder="Search by name…"
          value={query}
          onChange={v => setQuery(v)}
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
          <p className="py-8 text-center text-sm text-tertiary">No researchers found.</p>
        )}

        {data && data.researchers.length > 0 && (() => {
          const grouped = data.researchers.reduce<Record<string, { paper_count: number }>>((acc, r) => {
            if (!acc[r.display_name]) acc[r.display_name] = { paper_count: 0 };
            acc[r.display_name].paper_count += r.paper_count;
            return acc;
          }, {});
          const entries = Object.entries(grouped);
          return (
            <>
            <ul className="divide-y divide-secondary overflow-hidden rounded-xl ring-1 ring-primary shadow-sm">
              {entries.map(([name, info]) => (
                <li key={name} className="flex items-center justify-between bg-primary px-4 py-3">
                  <button
                    onClick={() => setSelectedName(name)}
                    className="text-sm font-medium text-primary hover:text-brand-secondary transition-colors text-left"
                  >
                    {name}
                  </button>
                  <span className="text-xs text-tertiary">{info.paper_count} papers</span>
                </li>
              ))}
            </ul>

            {data.pages > 1 && (
              <div className="mt-4 flex items-center justify-between text-sm text-tertiary">
                <button
                  onClick={() => goTo(page - 1)}
                  disabled={page <= 1}
                  className="flex items-center gap-1 rounded-lg px-3 py-1.5 ring-1 ring-secondary disabled:opacity-40 hover:bg-secondary transition-colors"
                >
                  <ChevronLeft className="size-4" /> Prev
                </button>
                <span>Page {data.page} / {data.pages}</span>
                <button
                  onClick={() => goTo(page + 1)}
                  disabled={page >= data.pages}
                  className="flex items-center gap-1 rounded-lg px-3 py-1.5 ring-1 ring-secondary disabled:opacity-40 hover:bg-secondary transition-colors"
                >
                  Next <ChevronRight className="size-4" />
                </button>
              </div>
            )}
          </>
          );
        })()}
      </div>

      {selectedName && (
        <ResearcherModal name={selectedName} onClose={() => setSelectedName(null)} />
      )}
    </div>
  );
}
