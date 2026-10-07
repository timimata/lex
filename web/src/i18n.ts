// The page's words in European Portuguese and in English. The law, the questions and the answers
// stay in Portuguese: only the interface around them changes.

export type Lang = "pt" | "en";

const pt = {
  tagline: "A lei do trabalho e do arrendamento, na versão em vigor em cada data",
  pages: { ask: "Perguntar", articles: "Artigos", results: "Resultados", about: "Sobre" },
  titles: {
    ask: "Lex: a lei do trabalho e do arrendamento, na versão em vigor em cada data",
    articles: "Artigos · Lex",
    results: "Resultados · Lex",
    about: "Sobre · Lex",
  },
  skip: "Saltar para o conteúdo",
  langSwitch: "Língua",
  disclaimer:
    "Os textos consolidados não têm valor legal: só faz fé a publicação no Diário da República. O Lex não é aconselhamento jurídico.",
  notice: "Textos consolidados sem valor legal; só faz fé o Diário da República. Não é aconselhamento jurídico.",
  unexpected: "Erro inesperado.",
  loading: "A carregar",
  // Ask
  askTitle: "Pergunte à lei do trabalho e do arrendamento",
  askLead:
    "A resposta assenta apenas nos artigos em vigor na data que indicar, e cada frase cita o seu artigo. Quando os artigos não permitem responder, o Lex di-lo.",
  question: "Pergunta",
  placeholder: "Escreva a sua pergunta sobre trabalho ou arrendamento",
  lawInForceOn: "Lei em vigor a",
  ask: "Perguntar",
  asking: "A consultar…",
  examples: "Exemplos",
  onDate: "em",
  searchingOn: "A consultar os artigos em vigor a",
  answer: "Resposta",
  noAnswer: "Sem resposta",
  lawOn: "lei em vigor a",
  cached: "resposta guardada",
  answered: "respondida em",
  retrievalShort: "pesquisa",
  modelShort: "modelo",
  answerLanguage: "",
  legalBasis: "Base legal",
  requestsTitle: "O que o modelo pediu antes de responder",
  modelCalls: (n: number) => (n === 1 ? "1 chamada ao modelo" : `${n} chamadas ao modelo`),
  inForceSince: "versão em vigor desde",
  copyLink: "Copiar ligação",
  copied: "Ligação copiada",
  newQuestion: "Nova pergunta",
  // The panel beside the question
  measuredTitle: "Medido num conjunto de teste",
  measuredLead:
    "Nenhum assistente de IA para a lei portuguesa que encontrámos publica quantas vezes acerta. O Lex mede-o num benchmark aberto, e os números são os desta demonstração.",
  correctShare: "respostas corretas",
  precisionShare: "citações corretas",
  testQuestions: "perguntas de teste, nunca usadas para afinar",
  seeResults: "Ver os resultados",
  runOf: "Execução de",
  howTitle: "Como responde",
  howShort: [
    "Guarda cada artigo em todas as versões, desde 2009 no trabalho e 2006 no arrendamento, com as datas de vigência.",
    "Procura os cinco artigos mais relevantes entre os em vigor na data.",
    "Um modelo responde só com base neles, cita-os, ou recusa.",
  ],
  // Reader
  diploma: "Diploma",
  nrau: "NRAU (Lei n.º 6/2006)",
  allDiplomas: "Todos os diplomas",
  notFound: "Página não encontrada",
  notFoundTitle: "Página não encontrada · Lex",
  notFoundLead: "Este endereço não corresponde a nenhuma página do Lex. Pode começar pela",
  notFoundHome: "página inicial",
  article: "Artigo",
  versionInForceOn: "Versão em vigor a",
  since: "desde",
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
  backToAnswer: "Voltar à resposta",
  close: "Fechar",
  // Articles
  browseTitle: "Consultar artigos",
  browseIntro:
    "Qualquer artigo na versão em vigor numa data, com o histórico de versões e as alterações. Esta consulta não usa modelos de linguagem.",
  browseLabel: "Artigo ou palavras",
  browsePlaceholder: "Ex.: 238, 199-A, NRAU 9, 1083 CC, férias, renda",
  browse: "Consultar",
  nothingFound: "Nenhum artigo em vigor nessa data contém essas palavras.",
  // Results
  loadingResults: "A carregar resultados…",
  resultsTitle: "Resultados",
  resultsIntro: (total: number, answerable: number, unanswerable: number) =>
    `Medidos num conjunto de teste de ${total} perguntas que nunca serviram para afinar o sistema: ${answerable} têm resposta nos diplomas do Lex e ${unanswerable} não têm.`,
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
  commit: "commit",
  thisDemo: "esta demonstração",
  summaryLine: (correct: string, precision: string, total: number) =>
    `Esta demonstração acertou ${correct} das ${total} perguntas de teste com resposta, e ${precision} das suas citações estavam certas.`,
  byType: "Resultados por tipo de pergunta",
  byTypeNote:
    "Cada tabela compara os sistemas num indicador, tipo a tipo. Recall e precisão são das citações; as recusas contam as perguntas que o sistema não respondeu.",
  type: "Tipo",
  questions: "Perguntas",
  recall: "Recall",
  refused: "Recusadas",
  correctShort: "Corretas",
  retrievalTitle: "Pesquisa de artigos",
  retrievalNote:
    "Parte das perguntas com resposta em que o artigo certo surge em 1.º lugar (recall@1) ou entre os 10 primeiros (recall@10).",
  namedArticle: "Perguntas que indicam o artigo",
  everyRun: "Todas as execuções, com configuração, modelos e custo",
  of: "de",
  types: {
    simple: "simples",
    composite: "compostas",
    temporal: "sobre uma data passada",
    explicit_reference: "com artigo indicado",
    unanswerable: "sem resposta nos diplomas do Lex",
  } as Record<string, string>,
  // Footer
  footerAbout: "Lex é um benchmark aberto e um sistema de referência para perguntas sobre legislação portuguesa.",
  footerSources: "Textos do Diário da República e da Procuradoria-Geral Distrital de Lisboa.",
  footerLinks: "Ligações",
  footerCode: "Código",
  footerDataset: "Benchmark (Hugging Face)",
  footerDR: "Diário da República",
  footerPGDL: "PGDL",
  footerLicences: "Licenças",
  footerLicenceText: "Código sob licença MIT; benchmark sob CC BY 4.0.",
  footerBy: "Por",
  systemOfDemo: "Sistema desta demonstração",
  // About
  about: {
    title: "Sobre o Lex",
    intro:
      "Existem assistentes de IA para a lei portuguesa, mas nenhum dos que encontrámos publica com que frequência acerta. O Lex é um benchmark aberto de perguntas sobre legislação portuguesa, em português europeu, cada uma com a data a que se refere e os artigos que uma resposta correta tem de citar, acompanhado de um sistema de referência medido nesse benchmark.",
    howTitle: "Como responde",
    how: [
      "Guarda cada artigo do Código do Trabalho em todas as versões desde 2009 e, sobre o arrendamento, os artigos 1022.º a 1113.º do Código Civil e o NRAU, com o histórico completo desde 2006, sempre com as respetivas datas de vigência.",
      "Procura os cinco artigos mais relevantes entre os que estavam em vigor na data indicada; um artigo mencionado na pergunta tem prioridade.",
      "Um modelo de linguagem responde apenas com base nesses artigos e cita-os; se nenhum o permitir, não responde.",
    ],
    demoRuns: "Esta demonstração usa",
    demoWhy:
      "a pesquisa corre sobre os artigos em memória, com embeddings da Gemini, sem servidor de modelos e sem custos. O sistema de referência do benchmark usa BGE-M3 e um reranker; os resultados de ambos estão em Resultados.",
    measuredTitle: "Como se mede",
    measured:
      "As perguntas vêm de páginas públicas (as FAQ e as notas técnicas da ACT, entre outras), nunca são inventadas, e cada uma tem a data a que se refere e os artigos a citar. Metade fica num conjunto de teste que nunca serve para afinar o sistema; os números publicados são os desse conjunto. Cada execução fica guardada com a configuração, os modelos e o custo. As decisões de desenho estão registadas uma a uma.",
    decisions: "Registo de decisões",
    runs: "Execuções",
    limitsTitle: "Limitações",
    limits: [
      "Abrange o Código do Trabalho e, no arrendamento, o Código Civil (artigos 1022.º a 1113.º) e o NRAU, e só o texto dos seus artigos: não inclui portarias, decretos complementares, convenções coletivas nem jurisprudência.",
      "As datas são as de entrada em vigor; normas transitórias e efeitos diferidos não estão representados.",
      "O número de perguntas por hora e por dia é limitado.",
    ],
    linksTitle: "Código e dados",
    codeLink: "Código, corpus e avaliação",
    datasetLink: "Benchmark, divisão de desenvolvimento",
    authorLine: "Feito por",
  },
};

export type Strings = typeof pt;

// Typed as the Portuguese, so a word missing in English fails the build.
const en: Strings = {
  tagline: "Portugal's labour and tenancy law, as in force on any date",
  pages: { ask: "Ask", articles: "Articles", results: "Results", about: "About" },
  titles: {
    ask: "Lex: Portugal's labour and tenancy law, as in force on any date",
    articles: "Articles · Lex",
    results: "Results · Lex",
    about: "About · Lex",
  },
  skip: "Skip to content",
  langSwitch: "Language",
  disclaimer:
    "Consolidated texts have no legal value: only the publication in the Diário da República is authentic. Lex is not legal advice.",
  notice: "Consolidated texts have no legal value; only the Diário da República is authentic. Not legal advice.",
  unexpected: "Unexpected error.",
  loading: "Loading",
  askTitle: "Ask the labour and tenancy law",
  askLead:
    "The answer rests only on the articles in force on the date you give, and every sentence cites its article. When the articles do not support an answer, Lex says so.",
  question: "Question (in Portuguese)",
  placeholder: "Type a question about work or renting, in Portuguese",
  lawInForceOn: "Law in force on",
  ask: "Ask",
  asking: "Consulting…",
  examples: "Examples",
  onDate: "on",
  searchingOn: "Consulting the articles in force on",
  answer: "Answer",
  noAnswer: "No answer",
  lawOn: "law in force on",
  cached: "stored answer",
  answered: "answered in",
  retrievalShort: "retrieval",
  modelShort: "model",
  answerLanguage: "Answers are in European Portuguese, the language of the law.",
  legalBasis: "Legal basis",
  requestsTitle: "What the model asked for before answering",
  modelCalls: (n: number) => (n === 1 ? "1 model call" : `${n} model calls`),
  inForceSince: "version in force since",
  copyLink: "Copy link",
  copied: "Link copied",
  newQuestion: "New question",
  measuredTitle: "Measured on a held-out test set",
  measuredLead:
    "No AI assistant for Portuguese law that we found publishes how often it is right. Lex measures it on an open benchmark, and these are this demo's own numbers.",
  correctShare: "correct answers",
  precisionShare: "correct citations",
  testQuestions: "test questions, never used for tuning",
  seeResults: "See the results",
  runOf: "Run of",
  howTitle: "How it answers",
  howShort: [
    "It keeps every article in every version, since 2009 for labour and 2006 for tenancy, with the dates in force.",
    "It retrieves the five most relevant articles among those in force on the date.",
    "A model answers from those alone, cites them, or refuses.",
  ],
  diploma: "Diploma",
  nrau: "NRAU (Lei n.º 6/2006)",
  allDiplomas: "All diplomas",
  notFound: "Page not found",
  notFoundTitle: "Page not found · Lex",
  notFoundLead: "This address is no page of Lex. You can start from the",
  notFoundHome: "home page",
  article: "Article",
  versionInForceOn: "Version in force on",
  since: "since",
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
  backToAnswer: "Back to the answer",
  close: "Close",
  browseTitle: "Look up articles",
  browseIntro:
    "Any article as in force on a date, with its version history and changes. No language model is involved.",
  browseLabel: "Article or words (in Portuguese)",
  browsePlaceholder: "E.g. 238, 199-A, NRAU 9, 1083 CC, férias, renda",
  browse: "Look up",
  nothingFound: "No article in force on that date contains those words.",
  loadingResults: "Loading results…",
  resultsTitle: "Results",
  resultsIntro: (total: number, answerable: number, unanswerable: number) =>
    `Measured on a held-out test set of ${total} questions never used to tune the system: ${answerable} are answerable from Lex's diplomas and ${unanswerable} are not.`,
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
  commit: "commit",
  thisDemo: "this demo",
  summaryLine: (correct: string, precision: string, total: number) =>
    `This demo got ${correct} of the ${total} answerable test questions right, and ${precision} of its citations were correct.`,
  byType: "Results by question type",
  byTypeNote:
    "Each table compares the systems on one measure, type by type. Recall and precision are the citations'; refused counts the questions the system did not answer.",
  type: "Type",
  questions: "Questions",
  recall: "Recall",
  refused: "Refused",
  correctShort: "Correct",
  retrievalTitle: "Article retrieval",
  retrievalNote:
    "Share of answerable questions whose right article comes first (recall@1) or among the first 10 (recall@10).",
  namedArticle: "Questions naming their article",
  everyRun: "Every run, with its configuration, models and cost",
  of: "of",
  types: {
    simple: "simple",
    composite: "composite",
    temporal: "about a past date",
    explicit_reference: "naming an article",
    unanswerable: "not answerable from Lex's diplomas",
  } as Record<string, string>,
  footerAbout: "Lex is an open benchmark and reference system for questions on Portuguese legislation.",
  footerSources: "Texts from the Diário da República and the Lisbon District Prosecutor's Office (PGDL).",
  footerLinks: "Links",
  footerCode: "Code",
  footerDataset: "Benchmark (Hugging Face)",
  footerDR: "Diário da República",
  footerPGDL: "PGDL",
  footerLicences: "Licences",
  footerLicenceText: "Code under the MIT licence; benchmark under CC BY 4.0.",
  footerBy: "By",
  systemOfDemo: "This demo's system",
  about: {
    title: "About Lex",
    intro:
      "Portugal has AI assistants for its law, but none we found publishes how often it is right. Lex is an open benchmark of questions on Portuguese legislation, in European Portuguese, each with the date it is asked about and the articles a correct answer must cite, together with a reference system measured on it.",
    howTitle: "How it answers",
    how: [
      "It keeps every article of the Labour Code in every version since 2009 and, on tenancy, articles 1022 to 1113 of the Civil Code and the NRAU, with their full history since 2006, always with the dates each version was in force.",
      "It retrieves the five most relevant articles among those in force on the date given; an article named in the question comes first.",
      "A language model answers from those articles only and cites them; if none supports an answer, it does not answer.",
    ],
    demoRuns: "This demo uses",
    demoWhy:
      "retrieval runs over the articles held in memory, with Gemini embeddings, with no model server and at no cost. The benchmark's reference system uses BGE-M3 and a reranker; both are scored under Results.",
    measuredTitle: "How it is measured",
    measured:
      "Questions come from public pages (the ACT's FAQ and technical notes, among others), are never invented, and each carries the date it is about and the articles to cite. Half go to a test set never used to tune the system; the published numbers are that set's. Every run is kept with its configuration, models and cost. Design decisions are recorded one by one.",
    decisions: "Decision records",
    runs: "Runs",
    limitsTitle: "Limitations",
    limits: [
      "It covers the Labour Code and, on tenancy, the Civil Code (articles 1022 to 1113) and the NRAU, and only their articles' text: no ordinances, implementing decrees, collective agreements or case law.",
      "Dates are when each version entered into force; transitional rules and deferred effects are not represented.",
      "Questions are limited per hour and per day.",
    ],
    linksTitle: "Code and data",
    codeLink: "Code, corpus builder and evaluation harness",
    datasetLink: "Benchmark, development split",
    authorLine: "Made by",
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
