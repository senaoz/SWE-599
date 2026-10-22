import { useState, useEffect } from "react";
import { SearchLg, XClose } from "@untitledui/icons";
import client from "../api/client";
import { ModalOverlay, Modal, Dialog } from "@/components/application/modals/modal";
import { Input } from "@/components/base/input/input";
import { Badge } from "@/components/base/badges/badges";

interface InstitutionResult {
  openalex_id: string;
  display_name: string;
  country_code: string | null;
}

interface Props {
  followedIds: Set<string>;
  onFollow: (inst: InstitutionResult) => Promise<void>;
  onClose: () => void;
}

export default function AddInstitutionModal({ followedIds, onFollow, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstitutionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    let stale = false;
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      client
        .get<InstitutionResult[]>("/institutions/openalex", { params: { q } })
        .then((r) => !stale && setResults(r.data))
        .catch(() => !stale && setError("Could not search OpenAlex. Try again."))
        .finally(() => !stale && setLoading(false));
    }, 300);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [query]);

  const tooShort = query.trim().length < 2;
  const shown = tooShort ? [] : results;

  const follow = async (inst: InstitutionResult) => {
    try {
      await onFollow(inst);
    } catch {
      setError(`Could not follow ${inst.display_name}.`);
    }
  };

  return (
    <ModalOverlay isOpen isDismissable onOpenChange={(open) => !open && onClose()}>
      <Modal className="max-w-xl">
        <Dialog aria-label="Add an institution">
          {() => (
            <div className="w-full max-w-xl overflow-hidden rounded-2xl bg-primary shadow-xl ring-1 ring-primary">
              <div className="flex items-start justify-between gap-4 border-b border-secondary px-6 py-4">
                <div>
                  <h2 className="text-lg font-semibold text-primary">Add an institution</h2>
                  <p className="mt-0.5 text-xs text-tertiary">
                    Search OpenAlex by name or paste an OpenAlex id (e.g. I4405392).
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Close"
                  onClick={onClose}
                  className="shrink-0 cursor-pointer rounded-md p-1 text-fg-quaternary transition-colors hover:text-fg-secondary"
                >
                  <XClose className="size-5" />
                </button>
              </div>

              <div className="max-h-[70vh] space-y-3 overflow-y-auto px-6 py-5">
                <Input
                  icon={SearchLg}
                  placeholder="e.g. ETH Zurich"
                  value={query}
                  onChange={(v) => setQuery(v)}
                  autoFocus
                />

                {!tooShort && loading && <p className="text-sm text-tertiary">Searching…</p>}
                {!tooShort && error && <p className="text-sm text-error-primary">{error}</p>}
                {!tooShort && !loading && !error && results.length === 0 && (
                  <p className="text-sm text-tertiary">
                    No institutions found. OpenAlex search needs the exact letters, so try "Boğaziçi" rather than "Bogazici".
                  </p>
                )}

                {shown.length > 0 && (
                  <ul className="divide-y divide-secondary overflow-hidden rounded-xl ring-1 ring-primary">
                    {shown.map((r) => (
                      <li key={r.openalex_id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="truncate font-medium text-primary">{r.display_name}</span>
                          {r.country_code && <span className="text-xs text-tertiary">{r.country_code}</span>}
                        </div>
                        {followedIds.has(r.openalex_id) ? (
                          <Badge color="gray" size="sm">
                            Following
                          </Badge>
                        ) : (
                          <div onClick={() => follow(r)} className="cursor-pointer">
                            <Badge color="success" size="sm">
                              Follow
                            </Badge>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
