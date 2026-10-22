import { useState, useEffect } from "react";
import { Plus, SearchLg } from "@untitledui/icons";
import client from "../api/client";
import { Input } from "@/components/base/input/input";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import AddInstitutionModal from "./AddInstitutionModal";

interface InstitutionResult {
  openalex_id: string;
  display_name: string;
  country_code: string | null;
}

interface Props {
  onFollow: (inst: InstitutionResult) => Promise<void>;
  followed: InstitutionResult[];
  onUnfollow: (id: string) => void;
}

export default function InstitutionSearch({
  onFollow,
  followed,
  onUnfollow,
}: Props) {
  const [query, setQuery] = useState("");
  const [curated, setCurated] = useState<InstitutionResult[]>([]);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    client
      .get<InstitutionResult[]>("/institutions/search", { params: { q: "" } })
      .then((r) => setCurated(r.data))
      .catch(() => setCurated([]));
  }, []);

  const followedIds = new Set(followed.map((f) => f.openalex_id));
  const curatedIds = new Set(curated.map((c) => c.openalex_id));
  // Institutions added from OpenAlex are listed after the curated ones.
  const all = [...curated, ...followed.filter((f) => !curatedIds.has(f.openalex_id))];

  const results =
    query.trim().length === 0
      ? all
      : all.filter((r) =>
          r.display_name.toLowerCase().includes(query.toLowerCase()),
        );

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
                <div onClick={() => onFollow(r)} className="cursor-pointer">
                  <Badge color="success" size="sm">
                    Follow
                  </Badge>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <div>
        <Button color="link-color" size="sm" iconLeading={Plus} onClick={() => setAdding(true)}>
          Add an institution not in the list
        </Button>
      </div>

      {adding && (
        <AddInstitutionModal
          followedIds={followedIds}
          onFollow={onFollow}
          onClose={() => setAdding(false)}
        />
      )}
    </div>
  );
}
