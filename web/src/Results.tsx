import type { Run } from "./api";
import { count, day, number, systemLabel } from "./labels";
import * as links from "./links";
import { useWords } from "./words";

/** The leaderboard: the newest test run of each system, from results/ (ADR 0016). */
export default function Results({ runs, error, demoSystem }: { runs: Run[] | null; error: string; demoSystem: string }) {
  const { lang, t } = useWords();

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
  const run = (r: Run) => (
    <td className="run" title={`${t.commit} ${r.commit}`}>
      {day(r.run_at.slice(0, 10))}
    </td>
  );
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

  // The demo's own run, said in words above the table.
  const demo = answers.find((r) => r.system === demoSystem);
  const demoCorrect = demo?.correctness?.answerable?.correta;
  const demoPrecision = demo?.summary.answerable?.citation_precision;
  const demoItems = demo?.summary.answerable?.items;
  const summary =
    demoCorrect != null && demoPrecision != null && demoItems
      ? t.summaryLine(`${Math.round(demoCorrect * 100)}%`, `${Math.round(demoPrecision * 100)}%`, demoItems)
      : null;

  // One matrix per measure: the question types as rows, the systems as columns.
  const measures: { title: string; cell: (r: Run, type: string) => string }[] = [
    ...(judged
      ? [{ title: t.correct, cell: (r: Run, type: string) => number(r.correctness?.[type]?.correta, lang) }]
      : []),
    { title: t.citationRecall, cell: (r, type) => number(r.summary[type]?.citation_recall, lang) },
    { title: t.precision, cell: (r, type) => number(r.summary[type]?.citation_precision, lang) },
    { title: t.refused, cell: (r, type) => count(r.summary[type]?.refused, r.summary[type]?.items, t.of) },
  ];
  const types = Object.entries(t.types).filter(([type]) => answers.some((r) => r.summary[type]));

  return (
    <section className="results">
      <header className="page-head">
        <h1>{t.resultsTitle}</h1>
        {sizes && <p className="lead">{t.resultsIntro(sizes.total, sizes.answerable, sizes.unanswerable)}</p>}
      </header>

      <section className="table-block">
        <h2>{t.answersTitle}</h2>
        {summary && <p className="summary">{summary}</p>}
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
                  {run(r)}
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
          <p className="note">{t.byTypeNote}</p>
          {measures.map((m) => (
            <div key={m.title} className="by-type">
              <h3>{m.title}</h3>
              <div className="table-scroll">
                <table className="data">
                  <thead>
                    <tr>
                      <th>{t.type}</th>
                      <th className="num">{t.questions}</th>
                      {answers.map((r) => (
                        <th key={r.run_at + r.system} className="num">
                          {systemLabel(r.system, lang)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {types.map(([type, label]) => (
                      <tr key={type}>
                        <td>{label}</td>
                        <td className="num">{answers[0]?.summary[type]?.items ?? "—"}</td>
                        {answers.map((r) => (
                          <td key={r.run_at + r.system} className="num">
                            {r.summary[type] ? m.cell(r, type) : "—"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </details>
      </section>

      <section className="table-block">
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
                  {run(r)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">{t.retrievalNote}</p>
        <p className="note">
          <a href={links.RESULTS}>{t.everyRun}</a>
        </p>
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
