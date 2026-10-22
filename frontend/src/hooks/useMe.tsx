import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import client from "../api/client";
import type { Me } from "../api/types";

interface MeContextValue {
  me: Me | null;
  /** Several ids for one person whose OpenAlex profile is split. */
  addFavorite: (researcherIds: string[]) => Promise<void>;
  removeFavorite: (researcherIds: string[]) => Promise<void>;
}

const MeContext = createContext<MeContextValue | null>(null);

/** The signed-in account and its favourite Boğaziçi researchers, shared by the navigation and the pages. */
export function MeProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    client
      .get<Me>("/auth/me")
      .then((r) => setMe(r.data))
      .catch((err) => console.error("Could not load the current user", err));
  }, []);

  const addFavorite = useCallback(async (researcherIds: string[]) => {
    for (const id of researcherIds) {
      const r = await client.put<Me>(`/auth/me/favorites/${id}`);
      setMe(r.data);
    }
  }, []);

  const removeFavorite = useCallback(async (researcherIds: string[]) => {
    for (const id of researcherIds) {
      const r = await client.delete<Me>(`/auth/me/favorites/${id}`);
      setMe(r.data);
    }
  }, []);

  return <MeContext.Provider value={{ me, addFavorite, removeFavorite }}>{children}</MeContext.Provider>;
}

export function useMe(): MeContextValue {
  const value = useContext(MeContext);
  if (!value) throw new Error("useMe must be used inside MeProvider");
  return value;
}
