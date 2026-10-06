# 0017. Tenancy: the Código Civil's chapter on leases and the NRAU

Date: 2026-10-01
Status: accepted

## Context

ADR 0003 left tenancy and the Código do IRS for Phase 6. Tenancy law sits in two diplomas:

- the **Código Civil** (Decreto-Lei n.º 47344, of 1966), Livro II, Título II, Capítulo IV,
  "Locação": articles 1022.º to 1063.º on leases in general, and 1064.º to 1113.º on urban
  leases, which the NRAU put back in the code in 2006 (Secção VII);
- the **NRAU** itself, Lei n.º 6/2006: communications between the parties, the special eviction
  procedure, the transitional rules for old contracts and their rents.

Both are read as the Código do Trabalho is (ADR 0005): every version from the PGDL
(`nid=775` and `nid=691`), dated and checked against the DR's consolidated pages
(`decreto-lei/1966-34509075` and `lei/2006-34578375`), rendered once and cached. Ingestion was
generalised for this: `src/lex/ingest/codes.py` holds what each diploma needs, and the rest of
the code names none. The Código do Trabalho rebuilds byte for byte.

What the two diplomas showed, on 2026-10-01:

1. **Old journals.** The DR's notes on the Código Civil go back to the Diário do Governo, to
   supplements and to Série I-A, and name acts whose number carries a letter: Decreto-Lei
   n.º 321-B/90 (the RAU) is not Decreto-Lei n.º 321/90. Diploma ids now keep the letter
   (`dl-321-b-1990`); five rectifications of 1975 to 1986 with no number at all are named by
   their journal issue (`retificacao-dg-236-1975`).
2. **An amending law.** The NRAU's articles 2.º to 8.º amend other codes and quote their articles
   in «...»; those quotes are text of the article that quotes them, not articles of the NRAU. The
   page ends with the signatures and an annex republishing the Código Civil's chapter as of 2006,
   neither of which is read.
3. **The PGDL's labels.** For 23 NRAU articles the PGDL credits a text to Lei n.º 79/2014, which
   republished the whole law, rather than to the act that changed the article (Lei n.º 31/2012,
   mostly): its texts are right and in order, its labels are not. And for 19 Código Civil
   articles (1064.º to 1082.º) it lacks a change the DR lists: their revocation in 1975 by
   Decreto-Lei n.º 201/75, before the NRAU restored them with new content. `build.py` now handles
   both: when the PGDL has as many texts as the DR lists changes, its texts are taken in order as
   those changes; when it lacks one, only the texts after the gap are kept.
4. **Spelling.** The PGDL's NRAU texts follow the 2014 republication, written under the 1990
   spelling agreement ("ação", "atualização"), while the DR consolidates over the 2006 text and
   keeps "acção" wherever no amendment reached. 27 of the 86 current texts differ this way. The
   current text is the DR's; an earlier version may read in the newer spelling.
5. **Dates.** The DR's own notes are wrong in three places, and `codes.py` corrects them with
   the reason: the Código Civil's art. 1073.º dated 2007-06-27 for Lei n.º 6/2006 (the other 61
   notes say 2006-06-27, and the law defers no article); the NRAU's art. 12.º rectified on
   2006-06-28 (a rectification takes effect with the text it rectifies, Lei n.º 74/98, art. 5.º,
   n.º 4); and 14 NRAU articles (38.º to 49.º, 55.º, 56.º) revoked by Lei n.º 31/2012 on
   2012-11-10, when the law revokes them in its art. 13.º with no date of its own and enters into
   force 90 days after its publication (art. 15.º), on 2012-11-12, as the DR's 44 other notes
   for it say. The NRAU's arts. 63.º and 64.º entered into force the day after publication,
   2006-02-28 (its art. 65.º, n.º 1).
6. **Undated changes.** The DR gives no date for three changes to the Código Civil before 2006:
   Decreto-Lei n.º 328/81, Lei n.º 24/89 and Decreto-Lei n.º 321-B/90, which revoked articles
   1083.º to 1120.º in 1990. An undated version cuts the history before it (ADR 0005), so 52
   Código Civil articles lack their history before 2006-06-27. Every tenancy article has its
   full history from that day, when the NRAU entered into force.
7. **Effects in part.** The DR records where another act defers or suspends part of an article:
   Lei n.º 56/2023 defers parts of NRAU arts. 15.º, 15.º-J, 15.º-M and 15.º-S to 2024-02-03;
   Lei n.º 19/2022 suspends the 2023 rent update coefficient (art. 24.º); Lei n.º 12/2022
   suspends deadlines of arts. 35.º and 36.º. These are not versions; the report lists them, as
   it now does for eight Código do Trabalho articles.
8. **A ruling.** Acórdão do Tribunal Constitucional n.º 299/2020 declared n.º 8 of the Código
   Civil's art. 1091.º unconstitutional with general binding force, from 2018-10-30.
9. **Spot checks.** Twelve earlier versions of each diploma, drawn at random, were compared with
   the DR's *Versão à data de* view on their first and last day in force
   ([Código Civil](../checks/cc-spot-check.md), [NRAU](../checks/nrau-spot-check.md)). The
   Código Civil's 24 checks all agree (2 differ in punctuation only). The NRAU's agree but for
   two, both on art. 35.º, where the DR's own history is wrong: for 2019 to 2023 it shows n.º 5
   in its 2012 wording and no alínea d), while Lei n.º 13/2019 added that alínea and neither it
   nor Lei n.º 43/2017 touched n.º 5 ("5 - ...", in both laws' text on the PGDL), which keeps
   the wording Lei n.º 79/2014 gave it until Lei n.º 56/2023 revoked it. The store follows the
   laws. The check now also tells apart texts that differ only in spelling (the 1990 agreement's
   silent consonants, in a republished text) and days on which the DR shows the next version,
   published but not yet in force.

## Decision

- The corpus holds the Código Civil's articles 1022.º to 1113.º (`dl-47344-1966`, 94 articles,
  147 versions) and the NRAU without its articles 2.º to 8.º (`lei-6-2006`, 86 articles, 177
  versions), next to the Código do Trabalho (601 articles, 889 versions).
- Dates follow ADR 0005's rules, plus the two corrections and the NRAU's own entry-into-force
  dates in `codes.py`, and the two rules for the PGDL's labels in `build.py`, each logged in
  `data/processed/<code>/report.json`.
- No `temporal` item asks about one of the 52 Código Civil articles before 2006-06-27, or about
  the parts of articles whose effects were deferred or suspended, over those periods. `validate`
  already refuses an item whose `must_cite` has no version on its date.
- Not now: the rest of the Código Civil, the decrees that complete the NRAU (Decretos-Leis
  n.os 157/2006, 160/2006 and 156/2015), and the Código do IRS, whose rules change with every
  State Budget and whose questions come from other sources. Questions that need them are
  `unanswerable`.

## Consequences

- An article number no longer names one article: the NRAU's 1.º to 65.º share numbers with the
  Código do Trabalho. References in questions, citations in answers and the demo's pages must
  say which diploma, and the reference parser (ADR 0004) must tell them apart.
- Systems are measured on a new corpus, so results on it are a new benchmark version, with
  tenancy items drawn, like the others, from public bodies' guidance.
- The weekly amendment check watches all three diplomas. The Código Civil's list of amending
  acts includes many that touch none of its articles on leases (a 2026 one among them), so a
  new one there means a person looks before the corpus is rebuilt.
