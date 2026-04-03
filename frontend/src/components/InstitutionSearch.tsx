import { useState, useEffect, useRef } from "react";
import { SearchLg } from "@untitledui/icons";
import client from "../api/client";
import { Input } from "@/components/base/input/input";
import { Button } from "@/components/base/buttons/button";
import { BadgeWithDot } from "@/components/base/badges/badges";

interface InstitutionResult {
  openalex_id: string;
  display_name: string;
  country_code: string | null;
}

interface Props {
  onFollow: (inst: InstitutionResult) => void;
  followedIds: Set<string>;
}

export default function InstitutionSearch({ onFollow, followedIds }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstitutionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (query.trim().length < 2) { setResults([]); return; }

    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await client.get("/institutions/search", { params: { q: query } });
        setResults(data as InstitutionResult[]);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 350);
  }, [query]);

  return (
    <div className="flex flex-col gap-3">
      <Input
        icon={SearchLg}
        placeholder="Search institutions (e.g. MIT, Stanford, DeepMind)…"
        value={query}
        onChange={(v) => setQuery(v)}
        isDisabled={false}
      />

      {loading && (
        <p className="text-sm text-tertiary">Searching…</p>
      )}

      {results.length > 0 && (
        <ul className="divide-y divide-secondary overflow-hidden rounded-xl ring-1 ring-primary shadow-sm">
          {results.map((r) => (
            <li
              key={r.openalex_id}
              className="flex items-center justify-between bg-primary px-4 py-3 text-sm"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium text-primary">{r.display_name}</span>
                {r.country_code && (
                  <span className="text-xs text-tertiary">{r.country_code}</span>
                )}
              </div>
              {followedIds.has(r.openalex_id) ? (
                <BadgeWithDot color="success" size="sm">Following</BadgeWithDot>
              ) : (
                <Button size="sm" color="primary" onClick={() => onFollow(r)}>
                  Follow
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
