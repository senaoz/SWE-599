import { useState } from "react";
import { Eye } from "@untitledui/icons";
import { Badge, BadgeWithIcon } from "@/components/base/badges/badges";
import client from "../api/client";
import type { MatchedWork, Paper, ResearcherMatch } from "../api/types";
import MatchLevel from "./MatchLevel";
import PaperMeta from "./PaperMeta";
import PaperModal from "./PaperModal";
import ResearcherModal from "./ResearcherModal";
import VerdictControl from "./VerdictControl";

const COLLAPSE_AFTER = 3;

interface Group {
  work: MatchedWork | null;
  researchers: ResearcherMatch[];
}

/** Researchers grouped by the BOUN work they were matched through, so one collaboration paper
 * with many BOUN authors reads as one reason, not five separate matches. */
function groupByWork(researchers: ResearcherMatch[]): Group[] {
  const groups: Group[] = [];
  const byWork = new Map<string, Group>();
  for (const r of researchers) {
    const work = r.matched_papers[0] ?? null;
    const existing = work ? byWork.get(work.work_id) : undefined;
    if (existing) {
      existing.researchers.push(r);
    } else {
      const group = { work, researchers: [r] };
      groups.push(group);
      if (work) byWork.set(work.work_id, group);
    }
  }
  return groups;
}

function WorkTitle({ work }: { work: MatchedWork }) {
  return (
    <>
      <span className="font-medium text-secondary italic">{work.title}</span>
      {work.year && <span className="text-quaternary"> ({work.year})</span>}
      {work.large_collaboration && (
        <span className="ml-1.5 align-middle" title="A work with 100 or more authors; a weak sign of personal expertise.">
          <Badge type="color" color="gray" size="sm">
            Collaboration
          </Badge>
        </span>
      )}
    </>
  );
}

function ExploreEvidence({ researchers, onResearcher }: { researchers: ResearcherMatch[]; onResearcher: (name: string) => void }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  return (
    <div className="space-y-2.5">
      {groupByWork(researchers).map((g, i) => {
        const open = expanded.has(i) || g.researchers.length <= COLLAPSE_AFTER;
        const shown = open ? g.researchers : g.researchers.slice(0, COLLAPSE_AFTER);
        return (
          <div key={i} className="text-sm">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {shown.map((r) => (
                <span key={r.researcher_id} className="inline-flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onResearcher(r.display_name);
                    }}
                    className="font-semibold text-primary hover:text-brand-secondary"
                  >
                    {r.display_name}
                  </button>
                  <MatchLevel score={r.score} />
                </span>
              ))}
              {!open && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setExpanded((s) => new Set(s).add(i));
                  }}
                  className="text-xs font-medium text-brand-secondary hover:underline"
                >
                  +{g.researchers.length - COLLAPSE_AFTER} more through the same work
                </button>
              )}
            </div>
            {g.work && (
              <p className="mt-0.5 text-xs text-tertiary">
                Matched through <WorkTitle work={g.work} />
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function FavoriteEvidence({ matches, onResearcher }: { matches: ResearcherMatch[]; onResearcher: (name: string) => void }) {
  return (
    <div className="space-y-4">
      {matches.map((match) => {
        const work = match.matched_papers[0];
        return (
          <div key={match.researcher_id} className="space-y-2">
            <div className="text-sm">
              <span className="inline-flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onResearcher(match.display_name);
                  }}
                  className="font-semibold text-primary hover:text-brand-secondary"
                >
                  {match.display_name}
                </button>
                <MatchLevel score={match.score} />
              </span>
              {work && (
                <p className="mt-0.5 text-xs text-tertiary">
                  Matched through <WorkTitle work={work} />
                </p>
              )}
            </div>
            <VerdictControl
              paperId={match.paper_openalex_id}
              researcherId={match.researcher_id}
              initial={match.my_verdict}
              initialReason={match.my_reason}
            />
          </div>
        );
      })}
    </div>
  );
}

interface PaperCardProps {
  paper: Paper;
  mode: "explore" | "forme";
}

export default function PaperCard({ paper, mode }: PaperCardProps) {
  const [seen, setSeen] = useState(paper.is_seen);
  const [modalOpen, setModalOpen] = useState(false);
  const [researcherName, setResearcherName] = useState<string | null>(null);

  const openModal = () => {
    setModalOpen(true);
    if (!seen) {
      setSeen(true);
      client
        .post(`/papers/${paper.openalex_id.replace("https://openalex.org/", "")}/seen`)
        .catch((err) => console.error("Could not mark the paper as seen", err));
    }
  };

  return (
    <>
      <article
        className={`mb-4 cursor-pointer rounded-xl p-5 ring-1 transition ${
          seen ? "bg-secondary_alt ring-secondary" : "bg-primary shadow-sm ring-primary hover:shadow-md"
        }`}
        onClick={openModal}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <PaperMeta
            institution={paper.source_institution_name}
            date={paper.publication_date}
            type={paper.type}
            hasAbstract={!!paper.abstract}
          />
          {seen && (
            <BadgeWithIcon type="color" color="gray" size="sm" iconLeading={Eye} className="ml-auto">
              Viewed
            </BadgeWithIcon>
          )}
        </div>

        <h2 className={`mb-1.5 text-md leading-snug ${seen ? "font-medium text-tertiary" : "font-semibold text-primary"}`}>
          {paper.title ?? "(No title)"}
        </h2>
        {paper.field && <p className="mb-2 text-xs text-quaternary">{paper.field}</p>}

        {paper.abstract && (
          <p className="mb-4 line-clamp-3 text-sm leading-relaxed text-tertiary">{paper.abstract}</p>
        )}

        <div className="border-t border-secondary pt-3">
          {mode === "forme" && paper.favorite_matches.length > 0 ? (
            <FavoriteEvidence matches={paper.favorite_matches} onResearcher={setResearcherName} />
          ) : paper.top_researchers.length > 0 ? (
            <ExploreEvidence researchers={paper.top_researchers} onResearcher={setResearcherName} />
          ) : (
            <p className="text-xs text-tertiary">No Boğaziçi researcher matched yet.</p>
          )}
        </div>
      </article>

      {modalOpen && <PaperModal paperId={paper.openalex_id} title={paper.title} onClose={() => setModalOpen(false)} />}
      {researcherName && <ResearcherModal name={researcherName} onClose={() => setResearcherName(null)} />}
    </>
  );
}
