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
  const [demoSystem, setDemoSystem] = useState<string>("");
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [runsError, setRunsError] = useState("");
  // Lisbon's date, from the server: the law asked about is Portuguese.
  const [serverToday, setServerToday] = useState<string>(today());
  const t = STRINGS[lang];

  useEffect(() => {
    api.health().then(
      (h) => {
        setDemoSystem(h.system);
        if (h.today) setServerToday(h.today);
      },
      () => setDemoSystem(""),
    );
    api.leaderboard().then(setRuns, (e: Error) => setRunsError(e.message));
    const back = () => setView(viewFromLocation());
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "pt" ? "pt-PT" : "en";
    document.title = t.titles[view];
  }, [lang, view, t]);

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
        {/* Kept mounted across views, so a question and its answer survive a look elsewhere. */}
        <div hidden={view !== "ask"}>
          <Ask latest={serverToday} demoRun={demoRun} onResults={() => go("results")} />
        </div>
        <div hidden={view !== "articles"}>
          <Browse latest={serverToday} />
        </div>
        <Suspense fallback={<p className="muted">{t.loading}…</p>}>
          {view === "results" && <Results runs={runs} error={runsError} demoSystem={demoSystem} />}
          {view === "about" && <About demoSystem={demoSystem} />}
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
            {timing && <p className="answer-details">{timing}</p>}
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
  const [diploma, setDiploma] = useState(linked.current?.citation.diploma ?? CT);
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
    if (found) {
      const citation = { diploma: found.diploma ?? diploma, article: found.article };
      if (found.diploma) setDiploma(found.diploma);
      setOpen({ citation, asOf });
      setLink("articles", { art: citation.article, dip: DIPLOMAS[citation.diploma].short, d: asOf, lang });
      return;
    }
    setOpen(null);
    try {
      setHits(await api.search(query, asOf));
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
}: {
  citation: Citation;
  asOf: string;
  backTo: string | null;
  onClose?: () => void;
}) {
  const { t } = useWords();
  const [shown, setShown] = useState(asOf);
  const [comparing, setComparing] = useState(false);
  useEffect(() => {
    setShown(asOf);
    setComparing(false);
  }, [asOf, citation]);
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
          </div>
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
