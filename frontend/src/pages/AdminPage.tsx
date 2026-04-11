import { useState, useEffect } from "react";
import { Lightning01, Settings01 } from "@untitledui/icons";
import client from "../api/client";
import { Button } from "@/components/base/buttons/button";

interface Status {
  paper_count: number;
  match_count: number;
  researcher_count: number;
  last_run_at: string | null;
}

export default function AdminPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [triggering, setTriggering] = useState(false);
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
      <div className="mb-8 grid grid-cols-3 gap-4">
        {stats.map(({ label, value }) => (
          <div
            key={label}
            className="flex flex-col items-center rounded-xl bg-primary p-5 shadow-sm ring-1 ring-primary text-center gap-1"
          >
            <span className="text-display-sm font-semibold text-brand-secondary">{value}</span>
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
      <section>
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
          isDisabled={triggering}
          onClick={trigger}
        >
          Run matching job now
        </Button>
      </section>
    </div>
  );
}
