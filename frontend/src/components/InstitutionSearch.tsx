import { useState, useEffect } from "react";
import { SearchLg } from "@untitledui/icons";
import client from "../api/client";
import { Input } from "@/components/base/input/input";
import { Button } from "@/components/base/buttons/button";
import { Badge } from "@/components/base/badges/badges";

interface InstitutionResult {
  openalex_id: string;
  display_name: string;
  country_code: string | null;
}

interface Props {
  onFollow: (inst: InstitutionResult) => void;
  followedIds: Set<string>;
  onUnfollow: (id: string) => void;
}

export default function InstitutionSearch({
  onFollow,
  followedIds,
  onUnfollow,
}: Props) {
  const [query, setQuery] = useState("");
  const [all, setAll] = useState<InstitutionResult[]>([]);

  useEffect(() => {
    client
      .get<InstitutionResult[]>("/institutions/search", { params: { q: "" } })
      .then((r) => setAll(r.data))
      .catch(() => setAll([]));
  }, []);

  const results =
    query.trim().length === 0
      ? all
      : all.filter((r) =>
          r.display_name.toLowerCase().includes(query.toLowerCase()),
        );

  console.log("results", { results, followedIds });

  return (
    <div className="flex flex-col gap-3">
      <Input
        icon={SearchLg}
        placeholder="Filter institutions…"
        value={query}
        onChange={(v) => setQuery(v)}
        isDisabled={false}
      />

      {results.length > 0 && (
        <ul className="divide-y divide-secondary overflow-hidden rounded-xl ring-1 ring-primary shadow-sm">
          {results.map((r) => (
            <li
              key={r.openalex_id}
              className="flex items-center justify-between bg-primary px-4 py-3 text-sm"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium text-primary">
                  {r.display_name}
                </span>
                {r.country_code && (
                  <span className="text-xs text-tertiary">
                    {r.country_code}
                  </span>
                )}
              </div>
              {followedIds.has(r.openalex_id) ? (
                <div
                  onClick={() => onUnfollow(r.openalex_id)}
                  className="cursor-pointer"
                >
                  <Badge color="error" size="sm">
                    Unfollow
                  </Badge>
                </div>
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
