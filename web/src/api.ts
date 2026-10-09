// The API's shapes (src/lex/api/app.py) and the calls the page makes.

import { STRINGS } from "./i18n";

export interface Citation {
  diploma: string;
  article: string;
}

export interface Reply {
  question: string;
  as_of: string;
  system: string;
  answer: {
    text: string;
    citations: Citation[];
    refused: boolean;
    timings?: Record<string, number>;
    // What the agent asked for before answering (ADR 0018), and the calls and tokens the answer took.
    requests?: string[];
    tokens?: Record<string, number>;
  };
  seconds: number; // measured on the server; 0 when cached
  cached: boolean;
  disclaimer: string;
}

export interface Period {
  valid_from: string;
  valid_to: string | null;
  introduced_by: string;
}

export interface ArticleView {
  diploma: string;
  article: string;
  as_of: string;
  heading: string | null;
  text: string | null;
  source_url: string | null;
  versions: Period[];
  notes?: string[]; // the DR's notes on the version's effects: deferred, suspended, ruled on
}

export type Row = Record<string, number | null>;

/** How the judge that scored a run's correctness was measured on dev (ADR 0015). */
export interface Judged {
  model: string;
  measured_on_dev: {
    known_answer_checks?: Record<"reference" | "altered", { as_expected: number; cases: number }>;
    hand_labels?: { items: number; agreement: number; kappa: number };
  };
}

export interface Run {
  system: string;
  task: "answers" | "retrieval";
  llm: string | null;
  run_at: string;
  commit: string;
  summary: Record<string, Row>;
  correctness: Record<string, Row> | null; // per type: shares judged correta, parcial, errada
  judge: Judged | null;
}

// The page's language, as App sets it on <html>: errors are worded in it.
const words = () => STRINGS[document.documentElement.lang.startsWith("en") ? "en" : "pt"];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const { errors } = words();
    // The API names each error by a code (X-Lex-Error), and when the quota renews.
    const code = response.headers.get("X-Lex-Error");
    const hour = response.headers.get("X-Lex-Renews") ?? "";
    let message = code && errors[code] ? errors[code].replace("{hour}", hour) : `Erro ${response.status}.`;
    if (!code) {
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
        else if (Array.isArray(body.detail)) message = errors.invalid;
      } catch {
        // not JSON: keep the status
      }
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export const ask = (question: string, asOf: string) =>
  call<Reply>("/api/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, as_of: asOf }),
  });

export const article = (c: Citation, asOf: string) =>
  call<ArticleView>(`/api/articles/${c.diploma}/${c.article}?as_of=${asOf}`);

export const leaderboard = () => call<Run[]>("/api/leaderboard");

export interface ChangeGroup {
  introduced_by: string;
  valid_from: string;
  articles: { article: string; heading: string; kind: "changed" | "added" | "revoked" | "original" }[];
}

export const changes = (diploma: string, since: string, until: string) =>
  call<{ groups: ChangeGroup[] }>(
    `/api/changes?diploma=${encodeURIComponent(diploma)}&since=${since}&until=${until}`,
  );

export const health = () => call<{ status: string; system: string; today?: string }>("/api/health");

export interface Hit {
  diploma: string;
  article: string;
  heading: string;
  excerpt?: string; // the line of the text that holds the words
  marks?: [number, number][]; // where they are in it
}

// `diploma` "" searches them all.
export const search = (q: string, asOf: string, diploma = "") =>
  call<Hit[]>(
    `/api/search?q=${encodeURIComponent(q)}&as_of=${asOf}` +
      (diploma ? `&diploma=${encodeURIComponent(diploma)}` : ""),
  );
