import { useState, useEffect } from "react";
import { Trash01 } from "@untitledui/icons";
import client from "../api/client";
import InstitutionSearch from "../components/InstitutionSearch";
import { Button } from "@/components/base/buttons/button";
import { EmptyState } from "@/components/application/empty-state/empty-state";

interface Institution { institution_openalex_id: string; institution_name: string; followed_at: string; }
interface SearchResult { openalex_id: string; display_name: string; country_code: string | null; }

export default function InstitutionsPage() {
  const [followed, setFollowed] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    client.get<Institution[]>("/institutions")
      .then(r => setFollowed(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const follow = async (inst: SearchResult) => {
    await client.post("/institutions", {
      institution_openalex_id: inst.openalex_id,
      institution_name: inst.display_name,
    });
    load();
  };

  const unfollow = async (id: string) => {
    await client.delete(`/institutions/${encodeURIComponent(id)}`);
    setFollowed(f => f.filter(i => i.institution_openalex_id !== id));
  };

  const followedIds = new Set(followed.map(f => f.institution_openalex_id));

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-8 text-xl font-semibold text-primary">Institutions</h1>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-tertiary uppercase tracking-wide">
          Search &amp; Follow
        </h2>
        <InstitutionSearch onFollow={follow} followedIds={followedIds} />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-tertiary uppercase tracking-wide">
          Following ({followed.length})
        </h2>

        {loading && <p className="text-sm text-tertiary">Loading…</p>}

        {!loading && followed.length === 0 && (
          <EmptyState size="sm">
            <EmptyState.Content>
              <EmptyState.Title>Not following anyone yet</EmptyState.Title>
              <EmptyState.Description>
                Search for institutions above and follow them.
              </EmptyState.Description>
            </EmptyState.Content>
          </EmptyState>
        )}

        {followed.length > 0 && (
          <ul className="flex flex-col gap-2">
            {followed.map(inst => (
              <li
                key={inst.institution_openalex_id}
                className="flex items-center justify-between rounded-xl bg-primary px-4 py-3 shadow-sm ring-1 ring-primary"
              >
                <div>
                  <p className="text-sm font-medium text-primary">{inst.institution_name}</p>
                  <p className="text-xs text-tertiary">
                    Since {new Date(inst.followed_at).toLocaleDateString()}
                  </p>
                </div>
                <Button
                  color="secondary-destructive"
                  size="sm"
                  iconLeading={Trash01}
                  onClick={() => unfollow(inst.institution_openalex_id)}
                >
                  Unfollow
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
