import { type ReactNode, Suspense, lazy, useEffect, useRef, useState } from "react";
import * as api from "./api";
import type { ArticleView, Citation, Hit, Period, Reply, Run } from "./api";
import { changes } from "./changes";
import examples from "./examples.json";
import { type Lang, STRINGS, initialLang, saveLang } from "./i18n";
import {
  CT,
  DIPLOMAS,
  FIRST_DAY,
  articleLabel,
  articleNumberLabel,
  day,
  diplomaLabel,
  number,
  systemLabel,
  today,
} from "./labels";
import * as links from "./links";
import { PATHS, type View, VIEWS, Words, useWords } from "./words";

// The pages a visitor reaches by a click, loaded then: the tables and the prose are not needed
// to ask a question.
const Results = lazy(() => import("./Results"));
const About = lazy(() => import("./About"));

// 'CT' -> 'lei-7-2009', for links and typed references.
const BY_SHORT: Record<string, string> = Object.fromEntries(
  Object.entries(DIPLOMAS).map(([id, d]) => [d.short, id]),
);

function same(a: Citation | null, b: Citation): boolean {
  return a !== null && a.diploma === b.diploma && a.article === b.article;
}

// Shared with vercel/assemble.py, which answers them at deploy so they come back at once.
const EXAMPLES: { question: string; asOf?: string }[] = examples;

/** The view a location names: its path, or the article link, which opens under Articles. */
function viewFromLocation(): View {
  if (linkedArticle()) return "articles";
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  return VIEWS.find((v) => PATHS[v] === path) ?? "ask";
}

/** Whether the address names no page (the server answers such a path with a 404). */
function pathMissing(): boolean {
  if (linkedArticle()) return false;
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  return !VIEWS.some((v) => PATHS[v] === path);
}

/** A question and date from the link (?q=...&d=...), so an answer can be shared. */
function linkedQuestion(): { question: string; asOf?: string } | null {
  const params = new URLSearchParams(window.location.search);
  const question = params.get("q")?.trim();
  if (!question) return null;
  const date = params.get("d") ?? undefined;
  return { question, asOf: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined };
}

/** An article and date from the link (?art=238&dip=CT&d=...), to share an article as it was. */
function linkedArticle(): { citation: Citation; asOf?: string } | null {
  const params = new URLSearchParams(window.location.search);
  const article = params.get("art");
  if (!article || !/^\d+(-[A-Z]{1,2})?$/i.test(article)) return null;
  const date = params.get("d") ?? undefined;
  return {
    citation: { diploma: BY_SHORT[params.get("dip") ?? "CT"] ?? CT, article: article.toUpperCase() },
    asOf: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined,
  };
}

/** "238", "art. 199.º-A", "artigo 1083.º do CC", "NRAU 9" -> the article and the diploma it
 * names, if any; anything else -> null. */
function articleRef(text: string): { article: string; diploma: string | null } | null {
  const shorts = Object.keys(BY_SHORT).join("|");
  const match = text
    .trim()
    .match(
      new RegExp(
        `^(?:(${shorts})\\s+)?(?:art(?:igo)?\\.?\\s*)?(\\d+)\\s*(?:\\.?º)?\\s*(?:-\\s*([a-z]{1,2}))?(?:\\s+(?:d[oa]\\s+)?(${shorts}))?$`,
        "i",
      ),
    );
  if (!match) return null;
  const article = match[3] ? `${Number(match[2])}-${match[3].toUpperCase()}` : String(Number(match[2]));
  const short = (match[1] ?? match[4])?.toUpperCase();
  return { article, diploma: short ? BY_SHORT[short] : null };
}

/** Points the address at a view, keeping only the given query (a question, an article). */
function setLink(view: View, params: Record<string, string>, push = false): void {
  const url = new URL(window.location.href);
  url.pathname = PATHS[view];
  url.search = new URLSearchParams(params).toString();
  if (push) window.history.pushState(null, "", url.toString());
  else window.history.replaceState(null, "", url.toString());
}

/** The answer's own text, and its list of sources ("Fontes (...):" lines), which the page shows
 * as a legal basis beside each cited article. */
function splitSources(text: string): { body: string; sources: { label: string; since: string | null }[] } {
  const at = text.indexOf("\n\nFontes (");
  if (at < 0) return { body: text, sources: [] };
  const sources = text
    .slice(at)
    .split("\n")
    .filter((line) => line.startsWith("- "))
    .map((line) => {
      const match = line.match(/^- (.*?) \(versão em vigor desde (\d{2}\/\d{2}\/\d{4})\)$/);
      return match ? { label: match[1], since: match[2] } : { label: line.slice(2), since: null };
    });
  return { body: text.slice(0, at), sources };
}

// "(art. 238.º do CT)", "(arts. 238.º e 239.º do CT)" or "(art. 1083.º do CC; art. 9.º do
// NRAU)" after a sentence of a per-sentence answer.
const MARKER = /\(arts?\. [^)]*\)/g;
const NUMBER = /(\d+)\.º(?:-([A-Z]{1,2}))?/g;

/** A line of an answer, each article in its citation markers a button that opens the article. */
function AnswerLine({
  line,
  citations,
  open,
  onOpen,
}: {
  line: string;
  citations: Citation[];
  open: Citation | null;
  onOpen: (c: Citation) => void;
}) {
  const pieces: ReactNode[] = [];
  let at = 0;
  for (const marker of line.matchAll(MARKER)) {
    const start = marker.index ?? 0;
    const text = marker[0];
    const parts: ReactNode[] = [];
    let inner = 0;
    for (const number of text.matchAll(NUMBER)) {
      const i = number.index ?? 0;
      const article = number[2] ? `${number[1]}-${number[2]}` : number[1];
      // The diploma the marker's part names after its numbers: "... do CC; ...".
      const part = text.slice(i).split(";")[0];
      const short = part.match(/ do ([A-Z]+)\)?\s*$/)?.[1];
      const diploma = short ? BY_SHORT[short] : undefined;
      const citation = citations.find(
        (c) => c.article === article && (diploma === undefined || c.diploma === diploma),
      );
      parts.push(text.slice(inner, i));
      parts.push(
        citation ? (
          <button
            key={i}
            type="button"
            className={citation && same(open, citation) ? "on" : ""}
            onClick={() => onOpen(citation)}
          >
            {number[0]}
          </button>
        ) : (
          number[0]
        ),
      );
      inner = i + number[0].length;
    }
    parts.push(text.slice(inner));
    pieces.push(line.slice(at, start));
    pieces.push(
      <span key={start} className="marker">
        {parts}
      </span>,
    );
    at = start + text.length;
  }
  pieces.push(line.slice(at));
  return <p>{pieces}</p>;
}

/** The azulejo as a mark: quarter circles meeting at the corners around a ring. */
function Mark() {
  return (
    <svg className="mark" viewBox="0 0 32 32" width="24" height="24" aria-hidden="true">
      <clipPath id="mark-clip">
        <rect width="32" height="32" rx="5" />
      </clipPath>
      <g clipPath="url(#mark-clip)">
        <rect width="32" height="32" fill="currentColor" />
        <g className="mark-ground">
          <circle r="8" />
          <circle cx="32" r="8" />
          <circle cy="32" r="8" />
          <circle cx="32" cy="32" r="8" />
          <circle cx="16" cy="16" r="3.2" />
        </g>
        <circle className="mark-ring" cx="16" cy="16" r="8.6" strokeWidth="2.2" />
      </g>
    </svg>
  );
}

export default function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  const [view, setView] = useState<View>(viewFromLocation);
  const [missing, setMissing] = useState(pathMissing);
  const [demoSystem, setDemoSystem] = useState<string>("");
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [runsError, setRunsError] = useState("");
  // Lisbon's date, from the server: the law asked about is Portuguese.
  const [serverToday, setServerToday] = useState<string>(today());
  const t = STRINGS[lang];
  // Set when the route changes, so focus moves to the new view (WCAG 2.4.3).
  const routed = useRef(false);

  useEffect(() => {
    api.health().then(
      (h) => {
        setDemoSystem(h.system);
        if (h.today) setServerToday(h.today);
      },
      () => setDemoSystem(""),
    );
    api.leaderboard().then(setRuns, (e: Error) => setRunsError(e.message));
    const back = () => {
      routed.current = true;
      setView(viewFromLocation());
      setMissing(pathMissing());
    };
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "pt" ? "pt-PT" : "en";
    document.title = missing ? t.notFoundTitle : t.titles[view];
  }, [lang, view, missing, t]);

  // After a route change, by the nav or back, focus starts at the new view's heading rather than
  // on the link left behind; a lazily loaded view gets a few frames to draw it.
  useEffect(() => {
    if (!routed.current) return;
    routed.current = false;
    const focus = (frames: number) => {
      // The views stay mounted, hidden: the heading is the one not inside a hidden view.
      const heading = Array.from(document.querySelectorAll<HTMLElement>("#content h1")).find(
        (h) => !h.closest("[hidden]"),
      );
      if (heading) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      } else if (frames > 0) requestAnimationFrame(() => focus(frames - 1));
    };
    requestAnimationFrame(() => focus(60));
  }, [view, missing]);

  function choose(next: Lang) {
    setLang(next);
    saveLang(next);
  }

  /** Opens a view from the nav: its path on the address, the question or article kept. */
  function go(next: View) {
    if (next !== view) {
      const url = new URL(window.location.href);
      url.pathname = PATHS[next];
      if (next !== "ask") url.searchParams.delete("q");
      if (next !== "articles") url.searchParams.delete("art");
      if (next !== "ask" && next !== "articles") url.searchParams.delete("d");
      window.history.pushState(null, "", url.toString());
    }
    routed.current = true;
    setMissing(false);
    setView(next);
    window.scrollTo({ top: 0 });
  }

  const demoRun = runs?.find((r) => r.task === "answers" && r.system === demoSystem) ?? null;

  return (
    <Words.Provider value={{ lang, t }}>
      <a className="skip" href="#content">
        {t.skip}
      </a>
      <header className="topbar">
        <div className="wrap topbar-inner">
          <a
            className="wordmark"
            href="/"
            onClick={(e) => {
              e.preventDefault();
              go("ask");
            }}
          >
            <Mark />
            <span className="wordmark-name">Lex</span>
            <span className="wordmark-tagline">{t.tagline}</span>
          </a>
          <nav className="nav" aria-label="Lex">
            {VIEWS.map((v) => (
              <a
                key={v}
                href={PATHS[v]}
                className={view === v ? "on" : ""}
                aria-current={view === v ? "page" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  go(v);
                }}
              >
                {t.pages[v]}
              </a>
            ))}
          </nav>
          <div className="lang-switch" role="group" aria-label={t.langSwitch}>
            {(["pt", "en"] as Lang[]).map((l) => (
              <button key={l} className={lang === l ? "on" : ""} aria-pressed={lang === l} onClick={() => choose(l)}>
                {l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </header>
      <p className="notice" role="note">
        <span className="wrap">{t.notice}</span>
      </p>

      <main id="content" className="wrap main">
        {missing && (
          <header className="page-head">
            <h1>{t.notFound}</h1>
            <p className="lead">
              {t.notFoundLead}{" "}
              <a href={PATHS.ask} onClick={(e) => (e.preventDefault(), go("ask"))}>
                {t.notFoundHome}
              </a>
              .
            </p>
          </header>
        )}
        {/* Kept mounted across views, so a question and its answer survive a look elsewhere. */}
        <div hidden={missing || view !== "ask"}>
          <Ask latest={serverToday} demoRun={demoRun} onResults={() => go("results")} />
        </div>
        <div hidden={missing || view !== "articles"}>
          <Browse latest={serverToday} />
        </div>
        <div hidden={missing || view !== "changes"}>
          <ChangesPage latest={serverToday} />
        </div>
        <Suspense fallback={<p className="muted">{t.loading}…</p>}>
          {!missing && view === "results" && <Results runs={runs} error={runsError} demoSystem={demoSystem} />}
          {!missing && view === "about" && <About demoSystem={demoSystem} />}
        </Suspense>
      </main>

      <footer className="site-footer">
        <div className="wrap footer-grid">
          <div className="footer-col">
            <p className="footer-about">{t.footerAbout}</p>
            <p>{t.footerSources}</p>
          </div>
          <div className="footer-col">
            <h2 className="footer-head">{t.footerLinks}</h2>
            <ul className="footer-links">
              <li>
                <a href={links.REPO}>{t.footerCode}</a>
              </li>
              <li>
                <a href={links.DATASET}>{t.footerDataset}</a>
              </li>
              <li>
                <a href={links.DR}>{t.footerDR}</a>
              </li>
              <li>
                <a href={links.PGDL}>{t.footerPGDL}</a>
              </li>
            </ul>
          </div>
          <div className="footer-col">
            <h2 className="footer-head">{t.footerLicences}</h2>
            <p>{t.footerLicenceText}</p>
            <p>
              {t.footerBy} {links.AUTHOR}.
            </p>
          </div>
        </div>
        <div className="wrap footer-legal">
          <p>{t.disclaimer}</p>
          {demoSystem && (
            <p>
              {t.systemOfDemo}: {systemLabel(demoSystem, lang)}.
            </p>
          )}
        </div>
      </footer>
    </Words.Provider>
  );
}

/** Beside the question: what the page is, and the demo's own numbers from the leaderboard. */
function Measured({ run, onResults }: { run: Run | null; onResults: () => void }) {
  const { lang, t } = useWords();
  const correct = run?.correctness?.answerable?.correta;
  const precision = run?.summary.answerable?.citation_precision;
  const answerable = run?.summary.answerable?.items;
  const unanswerable = run?.summary.unanswerable?.items;
  const total = answerable != null && unanswerable != null ? answerable + unanswerable : null;
  const figures = [
    { value: correct != null ? number(correct, lang) : null, label: t.correctShare },
    { value: precision != null ? number(precision, lang) : null, label: t.precisionShare },
    { value: total != null ? String(total) : null, label: t.testQuestions },
  ].filter((f) => f.value !== null);
  return (
    <aside className="measured" aria-label={t.measuredTitle}>
      {figures.length > 0 && (
        <>
          <h2 className="section-label">{t.measuredTitle}</h2>
          <p className="measured-lead">{t.measuredLead}</p>
          <dl className="figures">
            {figures.map((f) => (
              <div key={f.label}>
                <dt>{f.value}</dt>
                <dd>{f.label}</dd>
              </div>
            ))}
          </dl>
          <p>
            <a
              href={PATHS.results}
              onClick={(e) => {
                e.preventDefault();
                onResults();
              }}
            >
              {t.seeResults}
            </a>
            {run && (
              <span className="measured-run">
                {" "}
                · {t.runOf} {day(run.run_at.slice(0, 10))}
              </span>
            )}
          </p>
        </>
      )}
      <h2 className="section-label">{t.howTitle}</h2>
      <ol className="how">
        {t.howShort.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </aside>
  );
}

function Ask({ latest, demoRun, onResults }: { latest: string; demoRun: Run | null; onResults: () => void }) {
  const { lang, t } = useWords();
  const linked = useRef(linkedQuestion());
  const [question, setQuestion] = useState(linked.current?.question ?? "");
  const [asOf, setAsOf] = useState(linked.current?.asOf ?? latest);
  // The server's date arrives after the first render; follow it until a date is chosen.
  const [picked, setPicked] = useState(Boolean(linked.current?.asOf));
  useEffect(() => {
    if (!picked) setAsOf(latest);
  }, [latest, picked]);
  const [reply, setReply] = useState<Reply | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<Citation | null>(null);
  const [copied, setCopied] = useState(false);

  async function submit(q = question, date = asOf) {
    if (q.trim().length < 3) return;
    setBusy(true);
    setError("");
    setReply(null);
    setOpen(null);
    setCopied(false);
    try {
      const answer = await api.ask(q.trim(), date);
      setReply(answer);
      setLink("ask", { q: answer.question, d: answer.as_of, lang });
    } catch (e) {
      setError(e instanceof Error ? e.message : t.unexpected);
    } finally {
      setBusy(false);
    }
  }

  // A shared link asks its question once, when the page opens.
  useEffect(() => {
    if (linked.current) submit(linked.current.question, linked.current.asOf ?? latest);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const fmt = (n: number) => n.toLocaleString(lang === "pt" ? "pt-PT" : "en", { maximumFractionDigits: 2 });
  const stages = reply?.answer.timings;
  const timing =
    reply && !reply.cached
      ? `${t.answered} ${fmt(reply.seconds)} s` +
        (stages?.retrieval !== undefined && stages.generation !== undefined
          ? ` (${t.retrievalShort} ${fmt(stages.retrieval)} s, ${t.modelShort} ${fmt(stages.generation)} s)`
          : "")
      : "";
  const used = reply?.answer.tokens;
  const spent =
    used?.calls
      ? `${t.modelCalls(used.calls)}, ${(
          (used.prompt_tokens ?? 0) +
          (used.completion_tokens ?? 0) +
          (used.thinking_tokens ?? 0)
        ).toLocaleString(lang === "pt" ? "pt-PT" : "en")} tokens`
      : "";
  const details = [timing, spent].filter(Boolean).join(" · ");
  const requests = reply?.answer.requests ?? [];
  const { body, sources } = reply ? splitSources(reply.answer.text) : { body: "", sources: [] };
  const toggle = (c: Citation) => setOpen(same(open, c) ? null : c);
  const idle = !reply && !busy;

  return (
    <section className="ask">
      <div className={idle ? "home" : "home answered"}>
        <div className="home-main">
          <header className="page-head">
            <h1>{t.askTitle}</h1>
            <p className="lead">{t.askLead}</p>
          </header>
          <form
            className="query"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <label htmlFor="question" className="field-label">
              {t.question}
            </label>
            <textarea
              id="question"
              value={question}
              maxLength={1000}
              rows={2}
              placeholder={t.placeholder}
              aria-describedby="question-note"
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <div className="query-row">
              <label className="date-field">
                <span className="field-label">{t.lawInForceOn}</span>
                <input
                  type="date"
                  value={asOf}
                  min={FIRST_DAY}
                  max={latest}
                  onChange={(e) => {
                    setPicked(true);
                    setAsOf(e.target.value || latest);
                  }}
                />
              </label>
              <button type="submit" className="button primary" disabled={busy || question.trim().length < 3}>
                {busy ? t.asking : t.ask}
              </button>
            </div>
            <p id="question-note" className="query-note">
              {t.privacyNote}
            </p>
          </form>

          {idle && (
            <div className="examples">
              <h2 className="section-label">{t.examples}</h2>
              <ul>
                {EXAMPLES.map((ex) => (
                  <li key={ex.question}>
                    <button
                      type="button"
                      className="example"
                      onClick={() => {
                        const date = ex.asOf ?? latest;
                        setQuestion(ex.question);
                        setPicked(Boolean(ex.asOf));
                        setAsOf(date);
                        submit(ex.question, date);
                      }}
                    >
                      {ex.question}
                    </button>
                    {ex.asOf && (
                      <span className="muted">
                        {" "}
                        {t.onDate} {day(ex.asOf)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {busy && (
            <p className="status" aria-live="polite">
              {t.searchingOn} {day(asOf)}…
            </p>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </div>
        {idle && <Measured run={demoRun} onResults={onResults} />}
      </div>

      {reply && (
        <div className={open ? "workspace split" : "workspace"}>
          <article id="answer" className={reply.answer.refused ? "answer refused" : "answer"}>
            <div className="kicker">
              <span className="label">{reply.answer.refused ? t.noAnswer : t.answer}</span>
              <span className="kicker-meta">
                {t.lawOn} {day(reply.as_of)}
                {reply.cached && ` · ${t.cached}`}
              </span>
              <button type="button" className="text-button" onClick={copy}>
                {copied ? t.copied : t.copyLink}
              </button>
            </div>
            <h2 className="answer-question">{reply.question}</h2>
            {t.answerLanguage && <p className="note">{t.answerLanguage}</p>}
            <div className="answer-text" lang="pt-PT">
              {body.split("\n").map((line, i) =>
                line.trim() ? (
                  <AnswerLine key={i} line={line} citations={reply.answer.citations} open={open} onOpen={toggle} />
                ) : null,
              )}
            </div>
            {reply.answer.citations.length > 0 && (
              <section className="basis">
                <h3 className="section-label">{t.legalBasis}</h3>
                <ol>
                  {reply.answer.citations.map((c, i) => (
                    <li key={`${c.diploma}/${c.article}`} className={same(open, c) ? "on" : ""}>
                      <button type="button" className="cite" onClick={() => toggle(c)}>
                        {sources[i]?.label ?? articleLabel(c)}
                      </button>
                      {sources[i]?.since && (
                        <span className="muted">
                          {t.inForceSince} {sources[i].since}
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
              </section>
            )}
            {requests.length > 0 && (
              <section className="requests">
                <h3 className="section-label">{t.requestsTitle}</h3>
                <ol lang="pt-PT">
                  {requests.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ol>
              </section>
            )}
            {details && <p className="answer-details">{details}</p>}
          </article>
          {open && <Reader citation={open} asOf={reply.as_of} backTo="#answer" onClose={() => setOpen(null)} />}
        </div>
      )}
    </section>
  );
}

/** Any article on a date, by number or by words: no model, no quota. */
function Browse({ latest }: { latest: string }) {
  const { lang, t } = useWords();
  const linked = useRef(linkedArticle());
  const [query, setQuery] = useState(linked.current?.citation.article ?? "");
  // "" is every diploma: the default for words; a bare number is then looked up in each.
  const [diploma, setDiploma] = useState(linked.current?.citation.diploma ?? "");
  const [asOf, setAsOf] = useState(linked.current?.asOf ?? latest);
  const [picked, setPicked] = useState(Boolean(linked.current?.asOf));
  useEffect(() => {
    if (!picked) setAsOf(latest);
  }, [latest, picked]);
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [open, setOpen] = useState<{ citation: Citation; asOf: string } | null>(
    linked.current ? { citation: linked.current.citation, asOf: linked.current.asOf ?? latest } : null,
  );
  const [error, setError] = useState("");

  async function go() {
    setError("");
    setHits(null);
    const found = articleRef(query);
    const openAt = (citation: Citation) => {
      setOpen({ citation, asOf });
      setLink("articles", { art: citation.article, dip: DIPLOMAS[citation.diploma].short, d: asOf, lang });
    };
    if (found && (found.diploma || diploma)) {
      if (found.diploma) setDiploma(found.diploma);
      openAt({ diploma: found.diploma ?? diploma, article: found.article });
      return;
    }
    setOpen(null);
    try {
      if (found) {
        // A bare number with every diploma: the diplomas that have the article.
        const views = await Promise.allSettled(
          Object.keys(DIPLOMAS).map((d) => api.article({ diploma: d, article: found.article }, asOf)),
        );
        const have = Object.keys(DIPLOMAS).flatMap((d, i) => {
          const v = views[i];
          return v.status === "fulfilled" && v.value.versions.length
            ? [{ diploma: d, article: found.article, heading: v.value.heading ?? "" }]
            : [];
        });
        if (have.length === 1) openAt(have[0]);
        else if (have.length === 0) openAt({ diploma: CT, article: found.article });
        else setHits(have);
        return;
      }
      setHits(await api.search(query, asOf, diploma));
    } catch (e) {
      setError(e instanceof Error ? e.message : t.unexpected);
    }
  }

  return (
    <section className="browse">
      <header className="page-head">
        <h1>{t.browseTitle}</h1>
        <p className="lead">{t.browseIntro}</p>
      </header>
      <form
        className="query"
        onSubmit={(e) => {
          e.preventDefault();
          go();
        }}
      >
        <div className="query-row">
          <label className="text-field">
            <span className="field-label">{t.browseLabel}</span>
            <input
              id="browse"
              className="text-input"
              value={query}
              placeholder={t.browsePlaceholder}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label className="select-field">
            <span className="field-label">{t.diploma}</span>
            <select value={diploma} onChange={(e) => setDiploma(e.target.value)}>
              <option value="">{t.allDiplomas}</option>
              {Object.entries(DIPLOMAS).map(([id, d]) => (
                <option key={id} value={id}>
                  {d.short === "NRAU" ? t.nrau : d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="date-field">
            <span className="field-label">{t.lawInForceOn}</span>
            <input
              type="date"
              value={asOf}
              min={FIRST_DAY}
              max={latest}
              onChange={(e) => {
                setPicked(true);
                setAsOf(e.target.value || latest);
              }}
            />
          </label>
          <button type="submit" className="button primary" disabled={!query.trim()}>
            {t.browse}
          </button>
        </div>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className={hits?.length && open ? "workspace split" : "workspace"}>
        {hits && (
          <div id="hits">
            {hits.length === 0 ? (
              <p className="muted">{t.nothingFound}</p>
            ) : (
              <ol className="hits">
                {hits.map((h) => (
                  <li key={`${h.diploma}/${h.article}`} className={open && same(open.citation, h) ? "on" : ""}>
                    <button type="button" className="cite" onClick={() => setOpen({ citation: h, asOf })}>
                      {articleLabel(h)}
                    </button>
                    <span className="hit-heading">{h.heading}</span>
                    {h.excerpt && <Marked text={h.excerpt} marks={h.marks ?? []} />}
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
        {open && <Reader citation={open.citation} asOf={open.asOf} backTo={hits?.length ? "#hits" : null} />}
      </div>
    </section>
  );
}

/** What changed in a diploma between two dates: the laws that changed it and their articles. */
function ChangesPage({ latest }: { latest: string }) {
  const { lang, t } = useWords();
  const params = useRef(new URLSearchParams(window.location.search));
  const linked = window.location.pathname.startsWith(PATHS.changes);
  const fromLink = (name: string) => {
    const value = linked ? params.current.get(name) : null;
    return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
  };
  const [diploma, setDiploma] = useState(
    (linked && BY_SHORT[params.current.get("dip") ?? ""]) || "dl-47344-1966",
  );
  const [since, setSince] = useState(fromLink("de") ?? "2019-01-01");
  const [until, setUntil] = useState(fromLink("ate") ?? latest);
  const [groups, setGroups] = useState<api.ChangeGroup[] | null>(null);
  const [open, setOpen] = useState<{ citation: Citation; asOf: string; kind: string } | null>(null);
  const [error, setError] = useState("");

  async function go() {
    setError("");
    setOpen(null);
    setLink("changes", { dip: DIPLOMAS[diploma].short, de: since, ate: until, lang });
    try {
      setGroups((await api.changes(diploma, since, until)).groups);
    } catch (e) {
      setGroups(null);
      setError(e instanceof Error ? e.message : t.unexpected);
    }
  }

  // A shared link shows its period on arrival.
  useEffect(() => {
    if (linked && params.current.get("de")) go();
  }, []);

  return (
    <section className="changes">
      <header className="page-head">
        <h1>{t.changesTitle}</h1>
        <p className="lead">{t.changesIntro}</p>
      </header>
      <form
        className="query"
        onSubmit={(e) => {
          e.preventDefault();
          go();
        }}
      >
        <div className="query-row">
          <label className="select-field">
            <span className="field-label">{t.diploma}</span>
            <select value={diploma} onChange={(e) => setDiploma(e.target.value)}>
              {Object.entries(DIPLOMAS).map(([id, d]) => (
                <option key={id} value={id}>
                  {d.short === "NRAU" ? t.nrau : d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="date-field">
            <span className="field-label">{t.changesFrom}</span>
            <input type="date" value={since} min={FIRST_DAY} max={latest} onChange={(e) => setSince(e.target.value)} />
          </label>
          <label className="date-field">
            <span className="field-label">{t.changesUntil}</span>
            <input type="date" value={until} min={FIRST_DAY} max={latest} onChange={(e) => setUntil(e.target.value)} />
          </label>
          <button type="submit" className="button primary" disabled={!since || !until}>
            {t.changesShow}
          </button>
        </div>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className={groups?.length && open ? "workspace split" : "workspace"}>
        {groups && (
          <div id="changed">
            {groups.length === 0 ? (
              <p className="muted">{t.changesNone}</p>
            ) : (
              groups.map((g) => (
                <section key={`${g.introduced_by}/${g.valid_from}`} className="change-group">
                  <h2 className="change-law">
                    {diplomaLabel(g.introduced_by, diploma)}{" "}
                    <span className="muted">
                      {t.changesInForce} {day(g.valid_from)} · {t.changesCount(g.articles.length)}
                    </span>
                  </h2>
                  <ol className="hits">
                    {g.articles.map((a) => {
                      const citation = { diploma, article: a.article };
                      return (
                        <li key={a.article} className={open && same(open.citation, citation) ? "on" : ""}>
                          <button
                            type="button"
                            className="cite"
                            onClick={() => setOpen({ citation, asOf: g.valid_from, kind: a.kind })}
                          >
                            {articleLabel(citation)}
                          </button>
                          <span className="hit-heading">{a.heading}</span>
                          <span className={`change-kind ${a.kind}`}>{t.changeKinds[a.kind] ?? a.kind}</span>
                        </li>
                      );
                    })}
                  </ol>
                </section>
              ))
            )}
          </div>
        )}
        {open && (
          <Reader
            citation={open.citation}
            asOf={open.asOf}
            backTo="#changed"
            compare={open.kind === "changed" || open.kind === "revoked"}
          />
        )}
      </div>
    </section>
  );
}

/** Copies a link that opens this article as in force on this date, from any page. */
function CopyArticleLink({ citation, asOf }: { citation: Citation; asOf: string }) {
  const { lang, t } = useWords();
  const [copied, setCopied] = useState(false);
  useEffect(() => setCopied(false), [citation, asOf]);
  async function copy() {
    const url = new URL(PATHS.articles, window.location.origin);
    const dip = DIPLOMAS[citation.diploma]?.short ?? "CT";
    url.search = new URLSearchParams({ art: citation.article, dip, d: asOf, lang }).toString();
    try {
      await navigator.clipboard.writeText(url.toString());
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <button type="button" className="text-button" onClick={copy}>
      {copied ? t.copied : t.copyLink}
    </button>
  );
}

/** A hit's excerpt, the searched words marked. */
function Marked({ text, marks }: { text: string; marks: [number, number][] }) {
  const parts: ReactNode[] = [];
  let at = 0;
  for (const [start, end] of marks) {
    if (start < at || end > text.length) continue;
    parts.push(text.slice(at, start), <mark key={start}>{text.slice(start, end)}</mark>);
    at = end;
  }
  parts.push(text.slice(at));
  return (
    <span className="hit-excerpt" lang="pt-PT">
      {parts}
    </span>
  );
}

/** Fetches an article as of a date; a slower, older response never replaces a newer one. */
function useArticle(citation: Citation, asOf: string | null) {
  const [view, setView] = useState<ArticleView | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    setError("");
    setView(null);
    if (asOf === null) return;
    api.article(citation, asOf).then(
      (v) => current && setView(v),
      (e: Error) => current && setError(e.message),
    );
    return () => {
      current = false;
    };
  }, [citation, asOf]);
  return { view, error };
}

function inForce(p: Period, on: string): boolean {
  return p.valid_from <= on && (p.valid_to === null || on < p.valid_to);
}

/** How a line of an article is set: a numbered paragraph, a lettered item, or plain text. */
function lineKind(line: string): string {
  if (/^\s*\d+(?:\.º)?\s*-\s/.test(line)) return "para numbered";
  if (/^\s*[a-z]\)\s/.test(line)) return "para item";
  return "para";
}

function LegalText({ text }: { text: string }) {
  return (
    <div className="legal-text" lang="pt-PT">
      {text.split("\n").map((line, i) =>
        line.trim() ? (
          <p key={i} className={lineKind(line)}>
            {line}
          </p>
        ) : null,
      )}
    </div>
  );
}

function Reader({
  citation,
  asOf,
  backTo,
  onClose,
  compare = false,
}: {
  citation: Citation;
  asOf: string;
  backTo: string | null;
  onClose?: () => void;
  compare?: boolean; // open on the changes from the previous version
}) {
  const { t } = useWords();
  const [shown, setShown] = useState(asOf);
  const [comparing, setComparing] = useState(compare);
  useEffect(() => {
    setShown(asOf);
    setComparing(compare);
  }, [asOf, citation, compare]);
  const { view, error } = useArticle(citation, shown);

  const index = view ? view.versions.findIndex((p) => inForce(p, view.as_of)) : -1;
  const current = view && index >= 0 ? view.versions[index] : null;
  const previous = view && index > 0 ? view.versions[index - 1] : null;
  const before = useArticle(citation, comparing && previous ? previous.valid_from : null);
  const title = `${t.article} ${articleNumberLabel(citation.article)}`;

  return (
    <aside className="reader" aria-label={title}>
      <div className="reader-bar">
        <span className="reader-code">
          {DIPLOMAS[citation.diploma]?.short === "NRAU" ? t.nrau : DIPLOMAS[citation.diploma]?.name}
        </span>
        {backTo && (
          <a className="reader-back" href={backTo}>
            {t.backToAnswer}
          </a>
        )}
        {onClose && (
          <button type="button" className="text-button reader-close" onClick={onClose}>
            {t.close}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      {!error && !view && <p className="muted">{`${t.loading} ${articleLabel(citation)}…`}</p>}
      {view && (
        <>
          <h2 className="reader-title">{title}</h2>
          {view.heading && <p className="reader-heading">{view.heading}</p>}
          <p className="reader-meta">
            <span>
              {t.versionInForceOn} <b>{day(view.as_of)}</b>
            </span>
            {current && (
              <>
                <span>
                  {t.since} {day(current.valid_from)}
                  {current.valid_to && ` ${t.until} ${day(current.valid_to)}`}
                </span>
                <span>
                  {t.introducedBy} {diplomaLabel(current.introduced_by, citation.diploma)}
                </span>
              </>
            )}
          </p>
          <div className="reader-actions">
            {view.text &&
              (previous ? (
                <button type="button" className="text-button" onClick={() => setComparing(!comparing)}>
                  {comparing ? t.hideChanges : t.compare}
                </button>
              ) : (
                <span className="muted">{t.noPrevious}</span>
              ))}
            {view.source_url && (
              <a href={view.source_url} target="_blank" rel="noreferrer">
                {t.source}
              </a>
            )}
            <CopyArticleLink citation={citation} asOf={view.as_of} />
          </div>
          {view.notes && view.notes.length > 0 && (
            <div className="reader-notes">
              <p className="section-label">{t.notesTitle}</p>
              <ul>
                {view.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}
          {view.text ? (
            comparing && previous ? (
              <Changes before={before.view?.text ?? null} after={view.text} since={previous.valid_from} />
            ) : (
              <LegalText text={view.text} />
            )
          ) : (
            <p className="muted">{t.noVersion}</p>
          )}
          <section className="history">
            <h3 className="section-label">{t.versions}</h3>
            <ol className="timeline">
              {view.versions.map((p) => {
                const on = inForce(p, view.as_of);
                return (
                  <li key={p.valid_from} className={on ? "on" : ""}>
                    <button type="button" className="text-button" onClick={() => setShown(p.valid_from)}>
                      {day(p.valid_from)} – {p.valid_to ? day(p.valid_to) : t.today}
                    </button>
                    <span className="muted">{diplomaLabel(p.introduced_by, citation.diploma)}</span>
                    {on && <span className="tag">{t.shown}</span>}
                  </li>
                );
              })}
            </ol>
          </section>
        </>
      )}
    </aside>
  );
}

/** The article's text with what changed since the previous version marked, as in a redline. */
function Changes({ before, after, since }: { before: string | null; after: string; since: string }) {
  const { t } = useWords();
  if (before === null) return <p className="muted">{`${t.loading}…`}</p>;
  return (
    <div>
      <p className="note">
        {t.changesSince} {day(since)}: <ins>{t.legendAdded}</ins>, <del>{t.legendRemoved}</del>.
      </p>
      <div className="legal-text diff" lang="pt-PT">
        {changes(before, after).map((line, i) => (
          <p key={i} className={lineKind(line.map((piece) => piece.text).join(""))}>
            {line.map((piece, j) =>
              piece.kind === "added" ? (
                <ins key={j}>{piece.text}</ins>
              ) : piece.kind === "removed" ? (
                <del key={j}>{piece.text}</del>
              ) : (
                <span key={j}>{piece.text}</span>
              ),
            )}
          </p>
        ))}
      </div>
    </div>
  );
}
