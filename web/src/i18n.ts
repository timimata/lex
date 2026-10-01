// The page's words in European Portuguese and in English. The law, the questions and the answers
// stay in Portuguese: only the interface around them changes.

export type Lang = "pt" | "en";

const pt = {
  tagline: "Código do Trabalho, na versão em vigor em cada data",
  place: "Lisboa",
  tabs: { ask: "Perguntar", articles: "Artigos", results: "Resultados", about: "Sobre" },
  disclaimer:
    "Os textos consolidados não têm valor legal: só faz fé a publicação no Diário da República. O Lex não é aconselhamento jurídico.",
  footerAbout: "Lex é um benchmark aberto e um sistema de referência para perguntas sobre legislação portuguesa.",
  footerSources: "Fontes dos textos: Diário da República e Procuradoria-Geral Distrital de Lisboa.",
  systemOfDemo: "Sistema desta demonstração",
  unexpected: "Erro inesperado.",
  loading: "A carregar",
  // Ask
  askTitle: "Pergunte ao Código do Trabalho",
  askLead:
    "As respostas assentam apenas nos artigos em vigor na data que indicar, e cada uma mostra a sua base legal. Quando os artigos não permitem responder, o Lex di-lo.",
  question: "Pergunta",
  placeholder: "Escreva a sua pergunta sobre o Código do Trabalho",
  lawInForceOn: "Lei em vigor a",
  ask: "Perguntar",
  asking: "A consultar…",
  examples: "Perguntas de exemplo",
  onDate: "em",
  searchingOn: "A consultar os artigos em vigor a",
  answer: "Resposta",
  noAnswer: "Sem resposta",
  lawOn: "lei em vigor a",
  cached: "resposta guardada",
  retrievalShort: "pesquisa",
  modelShort: "modelo",
  answerLanguage: "",
  legalBasis: "Base legal",
  inForceSince: "versão em vigor desde",
  read: "Ler",
  copyLink: "Copiar ligação",
  copied: "Ligação copiada",
  // Reader
  code: "Código do Trabalho",
  article: "Artigo",
  versionInForceOn: "Versão em vigor a",
  since: "em vigor desde",
  until: "até",
  introducedBy: "redação de",
  noVersion: "Nenhuma versão deste artigo estava em vigor nessa data.",
  source: "Consultar na fonte",
  versions: "Histórico de versões",
  today: "hoje",
  shown: "em vigor nesta data",
  compare: "Ver alterações face à versão anterior",
  hideChanges: "Esconder alterações",
  changesSince: "Alterações face à versão em vigor desde",
  legendAdded: "texto introduzido",
  legendRemoved: "texto suprimido",
  noPrevious: "Primeira versão do artigo.",
  // Articles
  browseTitle: "Consultar artigos",
  browseIntro:
    "Consulte qualquer artigo na versão em vigor numa data, com o histórico de versões e as alterações. Esta consulta não usa modelos de linguagem.",
  browseLabel: "Artigo ou palavras",
  browsePlaceholder: "Ex.: 238, 199-A, férias, teletrabalho",
  browse: "Consultar",
  nothingFound: "Nenhum artigo em vigor nessa data contém essas palavras.",
  // Results
  loadingResults: "A carregar resultados…",
  resultsTitle: "Resultados",
  resultsIntro: (total: number, answerable: number, unanswerable: number) =>
    `Medidos num conjunto de teste de ${total} perguntas que nunca serviram para afinar o sistema: ${answerable} têm resposta no Código e ${unanswerable} não têm.`,
  answersTitle: "Respostas",
  answersNote:
    "Recall: parte dos artigos obrigatórios que a resposta cita. Precisão: parte das citações que estão corretas.",
  correct: "Respostas corretas",
  judgedByChecks: (model: string, references: string, altered: string) =>
    `Respostas corretas: avaliadas por um modelo (${model}) contra a resposta de referência de cada pergunta; com —, o sistema não foi avaliado. O avaliador não foi medido contra rótulos feitos por pessoas, mas em casos de resposta conhecida: aceitou ${references} respostas de referência e apanhou ${altered} respostas alteradas, com um número trocado ou o sim e o não invertidos. Mostra que apanha erros claros, não como avalia respostas ambíguas.`,
  judgedByLabels: (model: string, items: number, agreement: string, kappa: string) =>
    `Respostas corretas: avaliadas por um modelo (${model}) contra a resposta de referência de cada pergunta; com —, o sistema não foi avaliado. Em ${items} respostas rotuladas por uma pessoa, o avaliador concordou em ${agreement} (kappa de Cohen ${kappa}).`,
  system: "Sistema",
  citationRecall: "Recall das citações",
  precision: "Precisão das citações",
  wrongRefusals: "Recusas indevidas",
  rightRefusals: "Recusas corretas",
  run: "Execução",
  thisDemo: "esta demonstração",
  byType: "Resultados por tipo de pergunta",
  type: "Tipo",
  questions: "Perguntas",
  recall: "Recall",
  refused: "Recusadas",
  correctShort: "Corretas",
  retrievalTitle: "Pesquisa de artigos",
  retrievalNote:
    "Parte das perguntas com resposta em que o artigo certo surge em 1.º lugar (recall@1) ou entre os 10 primeiros (recall@10).",
  namedArticle: "Perguntas que indicam o artigo",
  of: "de",
  types: {
    simple: "simples",
    composite: "compostas",
    temporal: "sobre uma data passada",
    explicit_reference: "com artigo indicado",
    unanswerable: "sem resposta no Código",
  } as Record<string, string>,
  about: {
    title: "Sobre o Lex",
    intro:
      "Existem assistentes de IA para a lei portuguesa, mas nenhum dos que encontrámos publica com que frequência acerta. O Lex é um benchmark aberto de perguntas sobre legislação portuguesa, em português europeu, cada uma com a data a que se refere e os artigos que uma resposta correta tem de citar, acompanhado de um sistema de referência medido nesse benchmark.",
    howTitle: "Como responde",
    how: [
      "Guarda cada artigo do Código do Trabalho em todas as versões desde 2009, com as respetivas datas de vigência.",
      "Procura os cinco artigos mais relevantes entre os que estavam em vigor na data indicada; um artigo mencionado na pergunta tem prioridade.",
      "Um modelo de linguagem responde apenas com base nesses artigos e cita-os; se nenhum o permitir, não responde.",
    ],
    demoRuns: "Esta demonstração usa",
    demoWhy:
      "a pesquisa corre sobre os artigos em memória, com embeddings da Gemini, sem servidor de modelos e sem custos. O sistema de referência do benchmark usa BGE-M3 e um reranker; os resultados de ambos estão em Resultados.",
    limitsTitle: "Limitações",
    limits: [
      "Abrange apenas o Código do Trabalho e o texto dos seus artigos: não inclui portarias, convenções coletivas nem jurisprudência.",
      "As datas são as de entrada em vigor; normas transitórias e efeitos diferidos não estão representados.",
      "O número de perguntas por hora e por dia é limitado.",
    ],
  },
};

export type Strings = typeof pt;

// Typed as the Portuguese, so a word missing in English fails the build.
const en: Strings = {
  tagline: "Portugal's Labour Code, as in force on any date",
  place: "Lisbon",
  tabs: { ask: "Ask", articles: "Articles", results: "Results", about: "About" },
  disclaimer:
    "Consolidated texts have no legal value: only the publication in the Diário da República is authentic. Lex is not legal advice.",
  footerAbout: "Lex is an open benchmark and reference system for questions on Portuguese legislation.",
  footerSources: "Texts from the Diário da República and the Lisbon District Prosecutor's Office (PGDL).",
  systemOfDemo: "This demo's system",
  unexpected: "Unexpected error.",
  loading: "Loading",
  askTitle: "Ask the Labour Code",
  askLead:
    "Answers rest only on the articles in force on the date you give, and each shows its legal basis. When the articles do not support an answer, Lex says so.",
  question: "Question (in Portuguese)",
  placeholder: "Type a question about the Labour Code, in Portuguese",
  lawInForceOn: "Law in force on",
  ask: "Ask",
  asking: "Consulting…",
  examples: "Example questions",
  onDate: "on",
  searchingOn: "Consulting the articles in force on",
  answer: "Answer",
  noAnswer: "No answer",
  lawOn: "law in force on",
  cached: "stored answer",
  retrievalShort: "retrieval",
  modelShort: "model",
  answerLanguage: "Answers are in European Portuguese, the language of the law.",
  legalBasis: "Legal basis",
  inForceSince: "version in force since",
  read: "Read",
  copyLink: "Copy link",
  copied: "Link copied",
  code: "Labour Code",
  article: "Article",
  versionInForceOn: "Version in force on",
  since: "in force since",
  until: "until",
  introducedBy: "wording of",
  noVersion: "No version of this article was in force on that date.",
  source: "View at the source",
  versions: "Version history",
  today: "today",
  shown: "in force on this date",
  compare: "Show changes from the previous version",
  hideChanges: "Hide changes",
  changesSince: "Changes from the version in force since",
  legendAdded: "text added",
  legendRemoved: "text removed",
  noPrevious: "The article's first version.",
  browseTitle: "Look up articles",
  browseIntro:
    "Look up any article as in force on a date, with its version history and changes. No language model is involved.",
  browseLabel: "Article or words (in Portuguese)",
  browsePlaceholder: "E.g. 238, 199-A, férias, teletrabalho",
  browse: "Look up",
  nothingFound: "No article in force on that date contains those words.",
  loadingResults: "Loading results…",
  resultsTitle: "Results",
  resultsIntro: (total: number, answerable: number, unanswerable: number) =>
    `Measured on a held-out test set of ${total} questions never used to tune the system: ${answerable} are answerable from the Code and ${unanswerable} are not.`,
  answersTitle: "Answers",
  answersNote:
    "Recall: share of the required articles the answer cites. Precision: share of the citations that are correct.",
  correct: "Correct answers",
  judgedByChecks: (model: string, references: string, altered: string) =>
    `Correct answers: judged by a model (${model}) against each question's reference answer; a — means the system was not judged. The judge was measured not against human labels but on known-answer cases: it accepted ${references} reference answers and caught ${altered} altered ones, with a number changed or the yes and no turned over. That shows it catches clear errors, not how it judges ambiguous answers.`,
  judgedByLabels: (model: string, items: number, agreement: string, kappa: string) =>
    `Correct answers: judged by a model (${model}) against each question's reference answer; a — means the system was not judged. On ${items} answers labelled by a person, the judge agreed on ${agreement} (Cohen's kappa ${kappa}).`,
  system: "System",
  citationRecall: "Citation recall",
  precision: "Citation precision",
  wrongRefusals: "Wrong refusals",
  rightRefusals: "Right refusals",
  run: "Run",
  thisDemo: "this demo",
  byType: "Results by question type",
  type: "Type",
  questions: "Questions",
  recall: "Recall",
  refused: "Refused",
  correctShort: "Correct",
  retrievalTitle: "Article retrieval",
  retrievalNote:
    "Share of answerable questions whose right article comes first (recall@1) or among the first 10 (recall@10).",
  namedArticle: "Questions naming their article",
  of: "of",
  types: {
    simple: "simple",
    composite: "composite",
    temporal: "about a past date",
    explicit_reference: "naming an article",
    unanswerable: "not answerable from the Code",
  } as Record<string, string>,
  about: {
    title: "About Lex",
    intro:
      "Portugal has AI assistants for its law, but none we found publishes how often it is right. Lex is an open benchmark of questions on Portuguese legislation, in European Portuguese, each with the date it is asked about and the articles a correct answer must cite, together with a reference system measured on it.",
    howTitle: "How it answers",
    how: [
      "It keeps every article of the Labour Code in every version since 2009, with the dates each was in force.",
      "It retrieves the five most relevant articles among those in force on the date given; an article named in the question comes first.",
      "A language model answers from those articles only and cites them; if none supports an answer, it does not answer.",
    ],
    demoRuns: "This demo uses",
    demoWhy:
      "retrieval runs over the articles held in memory, with Gemini embeddings, with no model server and at no cost. The benchmark's reference system uses BGE-M3 and a reranker; both are scored under Results.",
    limitsTitle: "Limitations",
    limits: [
      "It covers only the Labour Code and its articles' text: no ordinances, collective agreements or case law.",
      "Dates are when each version entered into force; transitional rules and deferred effects are not represented.",
      "Questions are limited per hour and per day.",
    ],
  },
};

export const STRINGS: Record<Lang, Strings> = { pt, en };

/** The language to start in: the link's, then the visitor's last choice, then the browser's. */
export function initialLang(): Lang {
  const fromLink = new URLSearchParams(window.location.search).get("lang");
  if (fromLink === "pt" || fromLink === "en") return fromLink;
  try {
    const saved = window.localStorage.getItem("lex.lang");
    if (saved === "pt" || saved === "en") return saved;
  } catch {
    // storage blocked: fall through
  }
  return navigator.language.toLowerCase().startsWith("pt") ? "pt" : "en";
}

export function saveLang(lang: Lang): void {
  try {
    window.localStorage.setItem("lex.lang", lang);
  } catch {
    // storage blocked: the choice lasts for this visit only
  }
}
