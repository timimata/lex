// The page's views, their paths, and the words in the chosen language, shared by every page.

import { createContext, useContext } from "react";
import { type Lang, STRINGS, type Strings } from "./i18n";

export type View = "ask" | "articles" | "results" | "about";
export const VIEWS: View[] = ["ask", "articles", "results", "about"];
// The page's paths, which the API serves the page on (lex.api.app.PAGES).
export const PATHS: Record<View, string> = {
  ask: "/",
  articles: "/artigos",
  results: "/resultados",
  about: "/sobre",
};

export const Words = createContext<{ lang: Lang; t: Strings }>({ lang: "pt", t: STRINGS.pt });
export const useWords = () => useContext(Words);
