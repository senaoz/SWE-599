import { useState, useEffect, useCallback, type ReactNode } from "react";
import { AlertTriangle, CheckCircle, Clock, Lightning01, RefreshCcw01 } from "@untitledui/icons";
import client from "../api/client";
import PageHeader from "../components/PageHeader";
import { Button } from "@/components/base/buttons/button";
import { cx } from "@/utils/cx";

interface Status {
  paper_count: number;
  match_count: number;
  researcher_count: number;
  unmatched_count: number;
  last_run_at: string | null;
  embedding_version: string;
}

interface FeedbackSummary {
  embedding_version: string;
  total: number;
  by_rank: { rank: number; yes: number; partly: number; no: number }[];
  reasons: Record<string, number>;
}

const REASON_LABELS: Record<string, string> = {
  different_field: "Different field",
  too_general: "Too general",
  collaboration_only: "Only via a collaboration",
  same_author: "Same author",
};

/** Answers to "works on this topic?" by the rank the researcher was shown at: the app's only relevance signal. */
function FeedbackCard({ summary }: { summary: FeedbackSummary | null }) {
  return (
    <section className="rounded-xl bg-primary p-5 shadow-sm ring-1 ring-primary">
      <h2 className="text-md font-semibold text-primary">Feedback</h2>
      <p className="mt-1 mb-4 text-sm text-tertiary">
        Answers to "works on this topic?" at the current model version, by the rank the researcher was shown at.
      </p>
      {!summary || summary.total === 0 ? (
        <p className="text-sm text-tertiary">No answers yet.</p>
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-tertiary">
                <th className="pb-2 font-medium">Rank</th>
                <th className="pb-2 font-medium">Yes</th>
                <th className="pb-2 font-medium">Partly</th>
                <th className="pb-2 font-medium">No</th>
                <th className="pb-2 font-medium">Share yes</th>
              </tr>
            </thead>
            <tbody className="tabular-nums text-secondary">
              {summary.by_rank.map((r) => {
                const n = r.yes + r.partly + r.no;
                return (
                  <tr key={r.rank} className="border-t border-secondary">
                    <td className="py-1.5">{r.rank}</td>
                    <td>{r.yes}</td>
                    <td>{r.partly}</td>
                    <td>{r.no}</td>
                    <td>{n ? `${Math.round((100 * r.yes) / n)}% of ${n}` : "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {Object.keys(summary.reasons).length > 0 && (
            <p className="mt-3 text-xs text-tertiary">
              Reasons:{" "}
              {Object.entries(summary.reasons)
                .map(([k, n]) => `${REASON_LABELS[k] ?? k} ${n}`)
                .join(" · ")}
            </p>
          )}
          <p className="mt-2 text-xs text-quaternary">Small counts; read them as a direction, not a measurement.</p>
        </>
      )}
    </section>
  );
}

// The scheduled job runs every 6 hours (JOB_INTERVAL_HOURS); twice that without a fetch is worth a warning.
const STALE_AFTER_MS = 12 * 60 * 60 * 1000;
const POLL_MS = 10_000;
const POLL_FOR_MS = 60 * 60 * 1000;

function timeAgo(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function Callout({ tone, icon: Icon, children }: { tone: "warning" | "success" | "brand"; icon: typeof Clock; children: ReactNode }) {
  const styles = {
    warning: "bg-warning-primary text-warning-primary",
    success: "bg-success-primary text-success-primary",
    brand: "bg-brand-primary text-brand-secondary",
  };
  return (
    <div className={cx("flex items-start gap-3 rounded-xl px-4 py-3 text-sm ring-1 ring-secondary", styles[tone])}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

export default function AdminPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [feedback, setFeedback] = useState<FeedbackSummary | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [rematching, setRematching] = useState(false);
  const [startedAt, setStartedAt] = useState<{ kind: string; at: number } | null>(null);
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(() => {
    client
      .get<Status>("/admin/status")
      .then((r) => setStatus(r.data))
      .catch((err) =>
        setError(err.response?.status === 403 ? "This page is for admins only." : "Could not load the admin status."),
      );
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    client
      .get<FeedbackSummary>("/admin/feedback")
      .then((r) => setFeedback(r.data))
      .catch((err) => console.error("Could not load the feedback summary", err));
  }, []);

  // While a job started from here may still be running, refresh the counts and the elapsed time.
  useEffect(() => {
    if (!startedAt) return;
    const poll = setInterval(() => {
      if (Date.now() - startedAt.at > POLL_FOR_MS) setStartedAt(null);
      else load();
    }, POLL_MS);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [startedAt, load]);

  const start = async (kind: string, path: string, setBusy: (v: boolean) => void) => {
    setBusy(true);
    setActionError(null);
    try {
      await client.post(path);
      setStartedAt({ kind, at: Date.now() });
      setNow(Date.now());
    } catch {
      setActionError(`Could not start the ${kind}.`);
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-sm text-tertiary">{error}</p>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-sm text-tertiary">Loading…</p>
      </div>
    );
  }

  const lastRun = status.last_run_at;
  const stale = !lastRun || Date.now() - new Date(lastRun).getTime() > STALE_AFTER_MS;
  const elapsed = startedAt ? Math.floor((now - startedAt.at) / 1000) : 0;

  const stats = [
    { label: "Researchers", value: status.researcher_count },
    { label: "Papers fetched", value: status.paper_count },
    { label: "Matches", value: status.match_count },
    { label: "Papers without matches", value: status.unmatched_count, warn: status.unmatched_count > 0 },
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <PageHeader
        title="Admin"
        description={
          <>
            Matching status, feedback and manual runs. Model version{" "}
            <code className="rounded bg-secondary px-1 text-xs text-secondary">{status.embedding_version}</code>
          </>
        }
      />

      <div className="mb-6 space-y-3">
        {startedAt && (
          <Callout tone="brand" icon={Clock}>
            The {startedAt.kind} was started {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} ago.
            Counts refresh every {POLL_MS / 1000} s. Embedding takes a few seconds per new paper, and matches appear
            when the job ends.
          </Callout>
        )}
        {actionError && (
          <Callout tone="warning" icon={AlertTriangle}>
            {actionError}
          </Callout>
        )}
        {stale ? (
          <Callout tone="warning" icon={AlertTriangle}>
            {lastRun
              ? `The last fetch was ${timeAgo(lastRun)}; the scheduled job runs every 6 hours.`
              : "The matching job has not fetched any papers yet."}
          </Callout>
        ) : (
          <Callout tone="success" icon={CheckCircle}>
            <span title={new Date(lastRun!).toLocaleString()}>Last fetch {timeAgo(lastRun!)}.</span>
          </Callout>
        )}
      </div>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(({ label, value, warn }) => (
          <div key={label} className="flex flex-col gap-1 rounded-xl bg-primary p-4 shadow-sm ring-1 ring-primary">
            <span className="text-xs font-medium text-tertiary">{label}</span>
            <span className={cx("text-display-xs font-semibold tabular-nums", warn ? "text-warning-primary" : "text-primary")}>
              {value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>

      <div className="space-y-4">
        <FeedbackCard summary={feedback} />

        <section className="rounded-xl bg-primary p-5 shadow-sm ring-1 ring-primary">
          <h2 className="text-md font-semibold text-primary">Run the matching job</h2>
          <p className="mt-1 mb-4 text-sm text-tertiary">
            Fetches new papers from every followed institution, embeds them and matches them to Boğaziçi researchers.
          </p>
          <Button
            color="primary"
            size="md"
            iconLeading={Lightning01}
            isLoading={triggering}
            isDisabled={triggering || rematching}
            onClick={() => start("matching job", "/admin/trigger", setTriggering)}
          >
            Run matching job now
          </Button>
        </section>

        <section className="rounded-xl bg-primary p-5 shadow-sm ring-1 ring-primary">
          <h2 className="text-md font-semibold text-primary">Rematch papers without matches</h2>
          <p className="mt-1 mb-4 text-sm text-tertiary">
            Runs matching again for the {status.unmatched_count.toLocaleString()} papers that have no researcher yet.
          </p>
          <Button
            color="secondary"
            size="md"
            iconLeading={RefreshCcw01}
            isLoading={rematching}
            isDisabled={triggering || rematching || status.unmatched_count === 0}
            onClick={() => start("rematch", "/admin/rematch-unmatched", setRematching)}
          >
            Rematch {status.unmatched_count.toLocaleString()} papers
          </Button>
        </section>
      </div>
    </div>
  );
}
