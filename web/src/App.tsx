import { type ReactNode, createContext, useContext, useEffect, useRef, useState } from "react";
import * as api from "./api";
import type { ArticleView, Citation, Hit, Period, Reply, Run } from "./api";
import { changes } from "./changes";
import examples from "./examples.json";
import { type Lang, STRINGS, type Strings, initialLang, saveLang } from "./i18n";
import {
  FIRST_DAY,
  articleLabel,
  count,
  day,
  diplomaLabel,
  number,
  systemLabel,
  today,
} from "./labels";

type View = "ask" | "articles" | "results" | "about";
const VIEWS: View[] = ["ask", "articles", "results", "about"];
const CT = "lei-7-2009";

const Words = createContext<{ lang: Lang; t: Strings }>({ lang: "pt", t: STRINGS.pt });
const useWords = () => useContext(Words);

// Shared with vercel/assemble.py, which answers them at deploy so they come back at once.
const EXAMPLES: { question: string; asOf?: string }[] = examples;

/** A question and date from the link (?q=...&d=...), so an answer can be shared. */
function linkedQuestion(): { question: string; asOf?: string } | null {
  const params = new URLSearchParams(window.location.search);
  const question = params.get("q")?.trim();
  if (!question) return null;
  const date = params.get("d") ?? undefined;
  return { question, asOf: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined };
}

/** An article and date from the link (?art=238&d=...), to share an article as it was. */
function linkedArticle(): { article: string; asOf?: string } | null {
  const params = new URLSearchParams(window.location.search);
  const article = params.get("art");
  if (!article || !/^\d+(-[A-Z]{1,2})?$/i.test(article)) return null;
  const date = params.get("d") ?? undefined;
  return {
    article: article.toUpperCase(),
    asOf: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined,
  };
}

/** "238", "art. 199.º-A", "artigo 252-b" -> "238", "199-A", "252-B"; anything else -> null. */
function articleNumber(text: string): string | null {
  const match = text.trim().match(/^(?:art(?:igo)?\.?\s*)?(\d+)\s*(?:\.?º)?\s*(?:-\s*([a-z]{1,2}))?$/i);
  if (!match) return null;
  return match[2] ? `${Number(match[1])}-${match[2].toUpperCase()}` : String(Number(match[1]));
}

/** 2026-10-01 -> "quarta-feira, 1 de outubro de 2026" (or the English), for the masthead. */
function longDate(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(lang === "pt" ? "pt-PT" : "en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${iso}T12:00:00Z`));
}

function setLink(params: Record<string, string>): void {
  const url = new URL(window.location.href);
  url.search = new URLSearchParams(params).toString();
  window.history.replaceState(null, "", url.toString());
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

// "(art. 238.º)" or "(arts. 238.º e 239.º)" after a sentence of a per-sentence answer.
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
      const citation = citations.find((c) => c.article === article);
      parts.push(text.slice(inner, i));
      parts.push(
        citation ? (
          <button
            key={i}
            type="button"
            className={open?.article === article ? "on" : ""}
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

export default function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  const [view, setView] = useState<View>(linkedArticle() ? "articles" : "ask");
  const [demoSystem, setDemoSystem] = useState<string>("");
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
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "pt" ? "pt-PT" : "en";
  }, [lang]);

  function choose(next: Lang) {
    setLang(next);
    saveLang(next);
  }

  return (
    <Words.Provider value={{ lang, t }}>
      <header className="masthead">
        <div className="wrap masthead-inner">
          <a
            className="wordmark"
            href="/"
            onClick={(e) => {
              e.preventDefault();
              setView("ask");
            }}
          >
            <span className="wordmark-name">Lex</span>
            <span className="wordmark-tagline">{t.tagline}</span>
          </a>
          <div className="masthead-side">
            <span className="dateline">
              {t.place}, {longDate(serverToday, lang)}
            </span>
            <div className="lang-switch" role="group" aria-label="Língua / Language">
              {(["pt", "en"] as Lang[]).map((l) => (
                <button key={l} className={lang === l ? "on" : ""} aria-pressed={lang === l} onClick={() => choose(l)}>
                  {l.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>
      <nav className="navbar">
        <div className="wrap tabs">
          {VIEWS.map((v) => (
            <button
              key={v}
              className={view === v ? "tab on" : "tab"}
              aria-current={view === v ? "page" : undefined}
              onClick={() => setView(v)}
            >
              {t.tabs[v]}
            </button>
          ))}
        </div>
      </nav>

      <div className="notice" role="note">
        <p className="wrap">{t.disclaimer}</p>
      </div>

      <main className="wrap main">
        {/* Kept mounted across tabs, so a question and its answer survive a look elsewhere. */}
        <div hidden={view !== "ask"}>
          <Ask latest={serverToday} />
        </div>
        <div hidden={view !== "articles"}>
          <Browse latest={serverToday} />
        </div>
        {view === "results" && <Results demoSystem={demoSystem} />}
        {view === "about" && <About demoSystem={demoSystem} />}
      </main>

      <footer className="site-footer">
        <div className="wrap">
          <p>{t.footerAbout}</p>
          <p>{t.footerSources}</p>
          <p>{t.disclaimer}</p>
          {demoSystem && (
            <p>
              {t.systemOfDemo}: {systemLabel(demoSystem, lang)}
            </p>
          )}
        </div>
      </footer>
    </Words.Provider>
  );
}

function Ask({ latest }: { latest: string }) {
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
      setLink({ q: answer.question, d: answer.as_of, lang });
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
    reply &&
    (reply.cached
      ? t.cached
      : `${fmt(reply.seconds)} s` +
        (stages?.retrieval !== undefined && stages.generation !== undefined
          ? ` (${t.retrievalShort} ${fmt(stages.retrieval)} s, ${t.modelShort} ${fmt(stages.generation)} s)`
          : ""));
  const { body, sources } = reply ? splitSources(reply.answer.text) : { body: "", sources: [] };

  return (
    <section className="ask">
      <header className="page-head reveal d1">
        <h1>{t.askTitle}</h1>
        <p className="lead">{t.askLead}</p>
      </header>
      <form
        className="query reveal d2"
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
          rows={3}
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

      <div className="examples reveal d3">
        <h2 className="section-label">{t.examples}</h2>
        <ol>
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
                  — {t.onDate} {day(ex.asOf)}
                </span>
              )}
            </li>
          ))}
        </ol>
      </div>

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

      {reply && (
        <div className={open ? "workspace split" : "workspace"}>
          <article className={reply.answer.refused ? "answer refused" : "answer"}>
            <div className="kicker">
              <div className="kicker-meta">
                <span className="stamp">{reply.answer.refused ? t.noAnswer : t.answer}</span>
                <span>
                  {t.lawOn} {day(reply.as_of)} · {timing}
                </span>
              </div>
              <button type="button" className="text-button" onClick={copy}>
                {copied ? t.copied : t.copyLink}
              </button>
            </div>
            <h2 className="answer-question">{reply.question}</h2>
            {t.answerLanguage && <p className="note">{t.answerLanguage}</p>}
            <div className="answer-text" lang="pt-PT">
              {body.split("\n").map((line, i) =>
                line.trim() ? (
                  <AnswerLine
                    key={i}
                    line={line}
                    citations={reply.answer.citations}
                    open={open}
                    onOpen={(c) => setOpen(open?.article === c.article ? null : c)}
                  />
                ) : null,
              )}
            </div>
            {reply.answer.citations.length > 0 && (
              <section className="basis">
                <h3 className="section-label">{t.legalBasis}</h3>
                <ol>
                  {reply.answer.citations.map((c, i) => (
                    <li key={`${c.diploma}/${c.article}`} className={open?.article === c.article ? "on" : ""}>
                      <button type="button" className="cite" onClick={() => setOpen(open?.article === c.article ? null : c)}>
                        {sources[i]?.label ?? articleLabel(c)}
                      </button>
                      {sources[i]?.since && (
                        <span className="muted">
                          {" "}
                          — {t.inForceSince} {sources[i].since}
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </article>
          {open && <Reader citation={open} asOf={reply.as_of} />}
        </div>
      )}
    </section>
  );
}

/** Any article on a date, by number or by words: no model, no quota. */
function Browse({ latest }: { latest: string }) {
  const { lang, t } = useWords();
  const linked = useRef(linkedArticle());
  const [query, setQuery] = useState(linked.current?.article ?? "");
  const [asOf, setAsOf] = useState(linked.current?.asOf ?? latest);
  const [picked, setPicked] = useState(Boolean(linked.current?.asOf));
  useEffect(() => {
    if (!picked) setAsOf(latest);
  }, [latest, picked]);
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [open, setOpen] = useState<{ citation: Citation; asOf: string } | null>(
    linked.current
      ? { citation: { diploma: CT, article: linked.current.article }, asOf: linked.current.asOf ?? latest }
      : null,
  );
  const [error, setError] = useState("");

  async function go() {
    setError("");
    setHits(null);
    const found = articleNumber(query);
    if (found) {
      setOpen({ citation: { diploma: CT, article: found }, asOf });
      setLink({ art: found, d: asOf, lang });
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
      <header className="page-head reveal d1">
        <h1>{t.browseTitle}</h1>
        <p className="lead">{t.browseIntro}</p>
      </header>
      <form
        className="query reveal d2"
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
          <div>
            {hits.length === 0 ? (
              <p className="muted">{t.nothingFound}</p>
            ) : (
              <ol className="hits">
                {hits.map((h) => (
                  <li key={h.article} className={open?.citation.article === h.article ? "on" : ""}>
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
        {open && <Reader citation={open.citation} asOf={open.asOf} />}
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

function Reader({ citation, asOf }: { citation: Citation; asOf: string }) {
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
  const [numberPart, suffix] = citation.article.split("-");

  if (error)
    return (
      <aside className="reader">
        <p className="error">{error}</p>
      </aside>
    );
  if (!view)
    return (
      <aside className="reader">
        <p className="muted">{`${t.loading} ${articleLabel(citation)}…`}</p>
      </aside>
    );
  return (
    <aside className="reader" aria-label={`${t.article} ${citation.article}`}>
      <p className="reader-code">{t.code}</p>
      <h2 className="reader-title">
        {t.article} {numberPart}.º{suffix ? `-${suffix}` : ""}
      </h2>
      {view.heading && <p className="reader-heading">{view.heading}</p>}
      <p className="reader-meta">
        {t.versionInForceOn} {day(view.as_of)}
        {current && (
          <>
            {" "}
            · {t.since} {day(current.valid_from)} · {t.introducedBy} {diplomaLabel(current.introduced_by)}
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
                <span className="muted">{diplomaLabel(p.introduced_by)}</span>
                {on && <span className="tag">{t.shown}</span>}
              </li>
            );
          })}
        </ol>
      </section>
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

function Results({ demoSystem }: { demoSystem: string }) {
  const { lang, t } = useWords();
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.leaderboard().then(setRuns, (e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!runs) return <p className="muted">{t.loadingResults}</p>;
  // Ranked: answers by share judged correct (unjudged last), then citation recall; retrieval by
  // recall@10.
  const answers = runs
    .filter((r) => r.task === "answers")
    .sort(
      (a, b) =>
        (b.correctness?.answerable?.correta ?? -1) - (a.correctness?.answerable?.correta ?? -1) ||
        (b.summary.answerable?.citation_recall ?? 0) - (a.summary.answerable?.citation_recall ?? 0),
    );
  const retrieval = runs
    .filter((r) => r.task === "retrieval")
    .sort((a, b) => (b.summary.all?.["recall@10"] ?? 0) - (a.summary.all?.["recall@10"] ?? 0));
  const run = (r: Run) => `${day(r.run_at.slice(0, 10))} · ${r.commit}`;
  const judged = answers.find((r) => r.correctness && r.judge)?.judge;
  // The test set's size, as the answer runs counted it.
  const counted = answers[0]?.summary;
  const sizes =
    counted?.answerable?.items != null && counted.unanswerable?.items != null
      ? {
          answerable: counted.answerable.items,
          unanswerable: counted.unanswerable.items,
          total: counted.answerable.items + counted.unanswerable.items,
        }
      : null;
  const checks = judged?.measured_on_dev.known_answer_checks;
  const labels = judged?.measured_on_dev.hand_labels;
  const share = (n: number) => n.toLocaleString(lang === "pt" ? "pt-PT" : "en", { maximumFractionDigits: 2 });

  return (
    <section className="results">
      <header className="page-head reveal d1">
        <h1>{t.resultsTitle}</h1>
        {sizes && <p className="lead">{t.resultsIntro(sizes.total, sizes.answerable, sizes.unanswerable)}</p>}
      </header>

      <section className="table-block reveal d2">
        <h2>{t.answersTitle}</h2>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>{t.system}</th>
                {judged && <th className="num">{t.correct}</th>}
                <th className="num">{t.citationRecall}</th>
                <th className="num">{t.precision}</th>
                <th className="num">{t.wrongRefusals}</th>
                <th className="num">{t.rightRefusals}</th>
                <th>{t.run}</th>
              </tr>
            </thead>
            <tbody>
              {answers.map((r) => (
                <tr key={r.run_at + r.system}>
                  <td>
                    {systemLabel(r.system, lang)}
                    {r.system === demoSystem && <span className="tag">{t.thisDemo}</span>}
                  </td>
                  {judged &&
                    (r.correctness ? (
                      <Share value={r.correctness.answerable?.correta} />
                    ) : (
                      <td className="num muted-cell">—</td>
                    ))}
                  <Share value={r.summary.answerable?.citation_recall} />
                  <Share value={r.summary.answerable?.citation_precision} />
                  <td className="num">{count(r.summary.answerable?.refused, r.summary.answerable?.items, t.of)}</td>
                  <td className="num">{count(r.summary.unanswerable?.refused, r.summary.unanswerable?.items, t.of)}</td>
                  <td className="muted">{run(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">{t.answersNote}</p>
        {judged && checks && (
          <p className="note">
            {t.judgedByChecks(
              systemLabel(judged.model, lang),
              `${checks.reference.as_expected} ${t.of} ${checks.reference.cases}`,
              `${checks.altered.as_expected} ${t.of} ${checks.altered.cases}`,
            )}
          </p>
        )}
        {judged && !checks && labels && (
          <p className="note">
            {t.judgedByLabels(systemLabel(judged.model, lang), labels.items, share(labels.agreement), share(labels.kappa))}
          </p>
        )}
        <details>
          <summary>{t.byType}</summary>
          {answers.map((r) => (
            <div key={r.run_at + r.system} className="by-type">
              <h3>{systemLabel(r.system, lang)}</h3>
              <div className="table-scroll">
                <table className="data">
                  <thead>
                    <tr>
                      <th>{t.type}</th>
                      <th className="num">{t.questions}</th>
                      <th className="num">{t.recall}</th>
                      <th className="num">{t.precision}</th>
                      <th className="num">{t.refused}</th>
                      {r.correctness && <th className="num">{t.correctShort}</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(t.types).map(([type, label]) => {
                      const row = r.summary[type];
                      if (!row) return null;
                      return (
                        <tr key={type}>
                          <td>{label}</td>
                          <td className="num">{row.items}</td>
                          <td className="num">{number(row.citation_recall, lang)}</td>
                          <td className="num">{number(row.citation_precision, lang)}</td>
                          <td className="num">{count(row.refused, row.items, t.of)}</td>
                          {r.correctness && <td className="num">{number(r.correctness[type]?.correta, lang)}</td>}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </details>
      </section>

      <section className="table-block reveal d3">
        <h2>{t.retrievalTitle}</h2>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>{t.system}</th>
                <th className="num">recall@1</th>
                <th className="num">recall@10</th>
                <th className="num">{t.namedArticle}</th>
                <th>{t.run}</th>
              </tr>
            </thead>
            <tbody>
              {retrieval.map((r) => (
                <tr key={r.run_at + r.system}>
                  <td>{systemLabel(r.system, lang)}</td>
                  <Share value={r.summary.all?.["recall@1"]} />
                  <Share value={r.summary.all?.["recall@10"]} />
                  <td className="num">
                    {count(r.summary.explicit_reference?.["recall@10"], r.summary.explicit_reference?.items, t.of)}
                  </td>
                  <td className="muted">{run(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">{t.retrievalNote}</p>
      </section>
    </section>
  );
}

/** A share in a table: its figure, and a bar of its size. */
function Share({ value }: { value: number | null | undefined }) {
  const { lang } = useWords();
  return (
    <td className="num">
      <span className="share">
        <span className="share-track" aria-hidden="true">
          <span style={{ width: `${Math.max(0, Math.min(1, value ?? 0)) * 100}%` }} />
        </span>
        {number(value, lang)}
      </span>
    </td>
  );
}

function About({ demoSystem }: { demoSystem: string }) {
  const { lang, t } = useWords();
  return (
    <article className="prose reveal d1">
      <h1>{t.about.title}</h1>
      <p className="lead">{t.about.intro}</p>
      <h2>{t.about.howTitle}</h2>
      <ol>
        {t.about.how.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <p>
        {t.about.demoRuns} {demoSystem ? <strong>{systemLabel(demoSystem, lang)}</strong> : "Lex"}: {t.about.demoWhy}
      </p>
      <h2>{t.about.limitsTitle}</h2>
      <ul>
        {t.about.limits.map((limit) => (
          <li key={limit}>{limit}</li>
        ))}
      </ul>
    </article>
  );
}
