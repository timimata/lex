import { useEffect } from "react";
import { systemLabel } from "./labels";
import * as links from "./links";
import { useWords } from "./words";

export default function About({ demoSystem }: { demoSystem: string }) {
  const { lang, t } = useWords();
  // The footer links to the notice (/sobre#privacidade): the page draws after the browser
  // has looked for the anchor, so it is scrolled to here.
  useEffect(() => {
    const target = window.location.hash.slice(1);
    if (target) document.getElementById(target)?.scrollIntoView();
  }, []);
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
      <h2 id="privacidade">{t.about.privacyTitle}</h2>
      {t.about.privacy.map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
      <p>
        {t.about.privacyContact} <a href={`mailto:${links.CONTACT}`}>{links.CONTACT}</a>. {t.about.privacyRights}{" "}
        <a href={links.CNPD}>{t.about.cnpd}</a>.
      </p>
      <ul>
        <li>
          <a href={links.GEMINI_TERMS}>{t.about.geminiTerms}</a>
        </li>
        <li>
          <a href={links.VERCEL_PRIVACY}>{t.about.vercelPrivacy}</a>
        </li>
      </ul>
    </article>
  );
}
