import { useState, useEffect } from "react";
import { BookOpen01, ChevronLeft, ChevronRight } from "@untitledui/icons";
import client from "../api/client";
import PaperCard from "../components/PaperCard";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { Button } from "@/components/base/buttons/button";

interface Researcher { display_name: string; score: number; }
interface Paper {
  openalex_id: string; title: string | null; abstract: string | null;
  publication_date: string | null; source_institution_name: string | null;
  top_researchers: Researcher[];
}
interface PapersResponse { papers: Paper[]; total: number; page: number; pages: number; }

export default function DashboardPage() {
  const [data, setData] = useState<PapersResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    client.get<PapersResponse>("/papers", { params: { page, limit: 20 } })
      .then(r => { setData(r.data); setError(null); })
      .catch(() => setError("Failed to load papers"))
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) {
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

  if (!data || data.total === 0) {
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
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-primary">Latest Papers</h1>
        <span className="text-sm text-tertiary">{data.total} papers</span>
      </div>

      <div>
        {data.papers.map(p => <PaperCard key={p.openalex_id} {...p} />)}
      </div>

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
