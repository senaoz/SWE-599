export type Verdict = "yes" | "partly" | "no";
export type VerdictReason = "different_field" | "too_general" | "collaboration_only" | "same_author";

export interface MatchedWork {
  work_id: string;
  title: string | null;
  score: number;
  year: number | null;
  large_collaboration: boolean;
}

export interface ResearcherMatch {
  paper_openalex_id: string;
  researcher_id: string;
  display_name: string;
  score: number;
  rank: number;
  matched_papers: MatchedWork[];
  my_verdict: Verdict | null;
  my_reason: VerdictReason | null;
}

export interface Paper {
  openalex_id: string;
  title: string | null;
  abstract: string | null;
  publication_date: string | null;
  source_institution_name: string | null;
  doi: string | null;
  type: string | null;
  field: string | null;
  oa_url: string | null;
  top_researchers: ResearcherMatch[];
  my_match: ResearcherMatch | null;
  is_seen: boolean;
}

export interface PapersResponse {
  papers: Paper[];
  total: number;
  page: number;
  pages: number;
}

export interface PaperDetail extends Omit<Paper, "top_researchers" | "my_match" | "is_seen"> {
  all_researchers: ResearcherMatch[];
}

export interface ResearcherBrief {
  id: string;
  openalex_id: string;
  display_name: string;
  paper_count: number;
}

export interface Me {
  email: string;
  is_admin: boolean;
  researcher: ResearcherBrief | null;
}
