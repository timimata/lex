// The API's shapes (src/lex/api/app.py) and the calls the page makes.

export interface Citation {
  diploma: string;
  article: string;
}

export interface Reply {
  question: string;
  as_of: string;
  system: string;
  answer: { text: string; citations: Citation[]; refused: boolean; timings?: Record<string, number> };
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

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = `Erro ${response.status}.`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail))
        message = "Pedido inválido: a pergunta tem de ter entre 3 e 1000 caracteres, e a data tem de ser válida.";
    } catch {
      // not JSON: keep the status
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

export const health = () => call<{ status: string; system: string; today?: string }>("/api/health");

export interface Hit {
  diploma: string;
  article: string;
  heading: string;
}

export const search = (q: string, asOf: string) =>
  call<Hit[]>(`/api/search?q=${encodeURIComponent(q)}&as_of=${asOf}`);
