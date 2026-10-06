import { systemLabel } from "./labels";
import * as links from "./links";
import { useWords } from "./words";

export default function About({ demoSystem }: { demoSystem: string }) {
  const { lang, t } = useWords();
  return (
    <article className="prose">
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
      <h2>{t.about.measuredTitle}</h2>
      <p>{t.about.measured}</p>
      <ul>
        <li>
          <a href={links.RESULTS}>{t.about.runs}</a>
        </li>
        <li>
          <a href={links.DECISIONS}>{t.about.decisions}</a>
        </li>
      </ul>
      <h2>{t.about.limitsTitle}</h2>
      <ul>
        {t.about.limits.map((limit) => (
          <li key={limit}>{limit}</li>
        ))}
      </ul>
      <h2>{t.about.linksTitle}</h2>
      <ul>
        <li>
          <a href={links.REPO}>{t.about.codeLink}</a>
        </li>
        <li>
          <a href={links.DATASET}>{t.about.datasetLink}</a>
        </li>
      </ul>
      <p>
        {t.about.authorLine} {links.AUTHOR}.
      </p>
    </article>
  );
}
