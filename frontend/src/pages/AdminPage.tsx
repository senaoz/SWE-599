import { useState, useEffect } from "react";
import { Lightning01, Settings01, RefreshCcw01 } from "@untitledui/icons";
import client from "../api/client";
import { Button } from "@/components/base/buttons/button";

interface Status {
  paper_count: number;
  match_count: number;
  researcher_count: number;
  unmatched_count: number;
  last_run_at: string | null;
}

export default function AdminPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [rematching, setRematching] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    client.get<Status>("/admin/status").then(r => setStatus(r.data));
  }, []);

  const trigger = async () => {
    setTriggering(true);
    setMsg(null);
    await client.post("/admin/trigger");
    setMsg("Matching job started in background.");
    setTriggering(false);
  };

  const rematchUnmatched = async () => {
    setRematching(true);
    setMsg(null);
    await client.post("/admin/rematch-unmatched");
    setMsg(`Rematch job started for ${status?.unmatched_count ?? 0} unmatched papers.`);
    setRematching(false);
  };

  if (!status) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-sm text-tertiary">Loading…</p>
      </div>
    );
  }

  const stats = [
    { label: "Researchers", value: status.researcher_count },
    { label: "Papers fetched", value: status.paper_count },
    { label: "Matches", value: status.match_count },
    { label: "Unmatched", value: status.unmatched_count, highlight: status.unmatched_count > 0 },
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center gap-2">
        <Settings01 className="size-5 text-tertiary" />
        <h1 className="text-xl font-semibold text-primary">Admin</h1>
      </div>

      {msg && (
        <div className="mb-6 rounded-xl bg-success-primary px-4 py-3 text-sm font-medium text-success-primary ring-1 ring-success_subtle">
          {msg}
        </div>
      )}

      {/* Stats */}
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {stats.map(({ label, value, highlight }) => (
          <div
            key={label}
            className="flex flex-col items-center rounded-xl bg-primary p-5 shadow-sm ring-1 ring-primary text-center gap-1"
          >
            <span className={`text-display-sm font-semibold ${highlight ? "text-warning-primary" : "text-brand-secondary"}`}>
              {value}
            </span>
            <span className="text-xs text-tertiary">{label}</span>
          </div>
        ))}
      </div>

      {status.last_run_at && (
        <p className="mb-6 text-xs text-tertiary">
          Last job run: {new Date(status.last_run_at).toLocaleString()}
        </p>
      )}

      {/* Manual trigger */}
      <section className="mb-8">
        <h2 className="mb-1 text-sm font-semibold text-tertiary uppercase tracking-wide">
          Manual Job Trigger
        </h2>
        <p className="mb-4 text-sm text-tertiary">
          Runs the matching job immediately for all followed institutions.
        </p>
        <Button
          color="primary"
          size="md"
          iconLeading={Lightning01}
          isLoading={triggering}
          isDisabled={triggering || rematching}
          onClick={trigger}
        >
          Run matching job now
        </Button>
      </section>

      {/* Rematch unmatched */}
      <section>
        <h2 className="mb-1 text-sm font-semibold text-tertiary uppercase tracking-wide">
          Rematch Unmatched Papers
        </h2>
        <p className="mb-4 text-sm text-tertiary">
          Re-runs Stage 2 scoring for the {status.unmatched_count} papers that currently have no researcher matches.
        </p>
        <Button
          color="secondary"
          size="md"
          iconLeading={RefreshCcw01}
          isLoading={rematching}
          isDisabled={triggering || rematching || status.unmatched_count === 0}
          onClick={rematchUnmatched}
        >
          Rematch {status.unmatched_count} unmatched papers
        </Button>
      </section>
    </div>
  );
}
