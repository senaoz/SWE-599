import { useState, useEffect } from "react";
import client from "../api/client";
import InstitutionSearch from "../components/InstitutionSearch";
import PageHeader from "../components/PageHeader";

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
  }, []);

  const follow = async (inst: SearchResult) => {
    await client.post("/institutions", {
      institution_openalex_id: inst.openalex_id,
      institution_name: inst.display_name,
    });
    load();
  };

  const unfollow = async (id: string) => {
    const shortId = id.replace("https://openalex.org/", "");
    await client.delete(`/institutions/${shortId}`);
    setFollowed((f) => f.filter((i) => i.institution_openalex_id !== id));
  };

  const followedResults: SearchResult[] = followed.map((f) => ({
    openalex_id: f.institution_openalex_id,
    display_name: f.institution_name,
    country_code: null,
  }));

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <PageHeader
        title="Institutions"
        description="Follow institutions to see their new papers on your dashboard."
      />

      <InstitutionSearch
        onFollow={follow}
        followed={followedResults}
        onUnfollow={unfollow}
      />
    </div>
  );
}
