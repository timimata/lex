// How ids read on the page.

import type { Citation } from "./api";
import type { Lang } from "./i18n";

export const FIRST_DAY = "2009-02-17";

export function today(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** 2011-06-01 -> 01/06/2011 */
export function day(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

/** 199-A -> art. 199.º-A */
export function articleLabel(c: Citation): string {
  const [number, suffix] = c.article.split("-");
  return `art. ${number}.º${suffix ? `-${suffix}` : ""}`;
}

/** lei-23-2012 -> Lei n.º 23/2012 */
export function diplomaLabel(id: string): string {
  const match = id.match(/^(.*)-(\d+)-(\d{4})$/);
  if (!match) return id;
  const [, kind, number, year] = match;
  if (id === "lei-7-2009") return "Lei n.º 7/2009 (versão original)";
  const names: Record<string, string> = {
    lei: "Lei",
    dl: "Decreto-Lei",
    retificacao: "Declaração de Retificação",
  };
  return `${names[kind] ?? kind} n.º ${number}/${year}`;
}

const PARTS: Record<string, string> = {
  bm25: "BM25",
  "dense-bge-m3": "Dense (BGE-M3)",
  "dense-gemini-embedding-2": "Dense (Gemini Embedding 2)",
  rerank: "reranker",
  "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
  "gemma-4-E2B-it-Q4_0": "Gemma 4 E2B, local",
  "gemma-4-E4B-it-Q4_K_M": "Gemma 4 E4B, local",
  "gemma-4-26b-a4b-it": "Gemma 4 26B A4B",
};
const PARTS_BY_LANG: Record<Lang, Record<string, string>> = {
  pt: { refs: "referências explícitas", xrefs: "referências cruzadas", claims: "citação por frase" },
  en: { refs: "explicit references", xrefs: "cross-references", claims: "a citation per sentence" },
};

/** dense-bge-m3+rerank+refs+gemini-3.1-flash-lite -> Dense (BGE-M3) + reranker + ... */
export function systemLabel(id: string, lang: Lang = "pt"): string {
  return id
    .split("+")
    .map((part) => PARTS_BY_LANG[lang][part] ?? PARTS[part] ?? part.replace(/^k(\d+)$/, "top $1"))
    .join(" + ");
}

/** 0.9 -> "0,90" in Portuguese, "0.90" in English. */
export function number(value: number | null | undefined, lang: Lang = "pt"): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(lang === "pt" ? "pt-PT" : "en", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** A share of n items as a count: 0.04 of 50 -> "2 de 50". */
export function count(
  share: number | null | undefined,
  n: number | null | undefined,
  of = "de",
): string {
  if (share === null || share === undefined || !n) return "—";
  return `${Math.round(share * n)} ${of} ${n}`;
}
