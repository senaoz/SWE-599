import { useState, useEffect } from "react";
import { Lightning01, Settings01 } from "@untitledui/icons";
import client from "../api/client";
import { Button } from "@/components/base/buttons/button";
import { Badge } from "@/components/base/badges/badges";

interface Status {
  active_model: string; paper_count: number; match_count: number;
  researcher_count: number; last_run_at: string | null;
}
interface ModelInfo { key: string; label: string; description: string; requires_ollama: boolean; }

export default function AdminPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => {
    Promise.all([
      client.get<Status>("/admin/status"),
      client.get<ModelInfo[]>("/admin/models"),
    ]).then(([s, m]) => {
      setStatus(s.data);
      setModels(m.data);
      setSelectedModel(s.data.active_model);
    });
  };

  useEffect(() => { load(); }, []);

  const saveModel = async () => {
    setSaving(true);
    await client.put("/admin/models/active", { model: selectedModel });
    setSaving(false);
    setMsg("Model updated.");
    load();
  };

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

      {/* Model selection */}
      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-tertiary uppercase tracking-wide">
          Active Similarity Model
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-4">
          {models.map(m => (
            <label
              key={m.key}
              className={[
                "flex cursor-pointer flex-col gap-2 rounded-xl p-4 ring-2 transition-all",
                selectedModel === m.key
                  ? "bg-brand-section ring-brand"
                  : "bg-primary ring-primary hover:ring-secondary",
              ].join(" ")}
            >
              <input
                type="radio"
                name="model"
                value={m.key}
                checked={selectedModel === m.key}
                onChange={() => setSelectedModel(m.key)}
                className="sr-only"
              />
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-primary">{m.label}</span>
                {m.requires_ollama && (
                  <Badge type="color" color="warning" size="sm">Ollama</Badge>
                )}
              </div>
              <p className="text-xs text-tertiary">{m.description}</p>
            </label>
          ))}
        </div>
        <Button
          color="primary"
          size="md"
          iconLeading={Settings01}
          isLoading={saving}
          isDisabled={saving || selectedModel === status.active_model}
          onClick={saveModel}
        >
          Save model
        </Button>
      </section>

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
