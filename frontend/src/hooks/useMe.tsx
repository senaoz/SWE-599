import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import client from "../api/client";
import type { Me } from "../api/types";

interface MeContextValue {
  me: Me | null;
  claim: (researcherId: string) => Promise<void>;
  unclaim: () => Promise<void>;
}

const MeContext = createContext<MeContextValue | null>(null);

/** The signed-in account and its claimed Boğaziçi profile, shared by the navigation and the pages. */
export function MeProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    client
      .get<Me>("/auth/me")
      .then((r) => setMe(r.data))
      .catch((err) => console.error("Could not load the current user", err));
  }, []);

  const claim = useCallback(async (researcherId: string) => {
    const r = await client.put<Me>("/auth/me/researcher", { researcher_id: researcherId });
    setMe(r.data);
  }, []);

  const unclaim = useCallback(async () => {
    const r = await client.delete<Me>("/auth/me/researcher");
    setMe(r.data);
  }, []);

  return <MeContext.Provider value={{ me, claim, unclaim }}>{children}</MeContext.Provider>;
}

export function useMe(): MeContextValue {
  const value = useContext(MeContext);
  if (!value) throw new Error("useMe must be used inside MeProvider");
  return value;
}
