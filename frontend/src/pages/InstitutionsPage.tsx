import { useState, useEffect } from "react";
import client from "../api/client";
import InstitutionSearch from "../components/InstitutionSearch";

interface Institution {
  institution_openalex_id: string;
  institution_name: string;
  followed_at: string;
}
interface SearchResult {
  openalex_id: string;
  display_name: string;
  country_code: string | null;
}

export default function InstitutionsPage() {
  const [followed, setFollowed] = useState<Institution[]>([]);

  const load = () => {
    client.get<Institution[]>("/institutions").then((r) => setFollowed(r.data));
  };

  useEffect(() => {
    load();

    console.log("followed", followed);
  }, []);

  const follow = async (inst: SearchResult) => {
    await client.post("/institutions", {
      institution_openalex_id: inst.openalex_id,
      institution_name: inst.display_name,
    });
    load();
  };

  const unfollow = async (id: string) => {
    // id = id.replace("https://openalex.org/", "");
    await client.delete(`/institutions/${encodeURIComponent(id)}`);
    setFollowed((f) => f.filter((i) => i.institution_openalex_id !== id));
  };

  const followedIds = new Set(followed.map((f) => f.institution_openalex_id));

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-8 text-xl font-semibold text-primary">Institutions</h1>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-tertiary uppercase tracking-wide">
          Search &amp; Follow
        </h2>
        <InstitutionSearch
          onFollow={follow}
          followedIds={followedIds}
          onUnfollow={unfollow}
        />
      </section>
    </div>
  );
}
