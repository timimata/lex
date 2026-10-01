# 0005. Consolidated text and article history come from the PGDL, checked against the DR

Date: 2026-09-29
Status: accepted

## Context

ADR 0002 needs every version of every article of the Código do Trabalho, with the diploma that
introduced it. We looked at two sources on 2026-09-29.

**diariodarepublica.pt (DR)** is the official journal and our reference for what the law says.
Its consolidated legislation pages are an OutSystems single-page app: the HTML served is an empty
shell, and the content arrives from undocumented internal endpoints. There is no `robots.txt`
(the path redirects to an error page), and we found no public API or bulk export for consolidated
text. The amending diplomas themselves are published as static PDFs on files.diariodarepublica.pt.

**pgdlisboa.pt (PGDL)**, the legislation base of the Procuradoria-Geral Regional de Lisboa, serves
the Código do Trabalho as plain server-rendered HTML (ISO-8859-1):

- `lei_mostra_articulado.php?nid=1047&tabela=leis` lists all 601 articles, each with a stable id
  (`1047A0238`, `1047A0252A`), and 24 versions of the whole code, each labelled with the diploma
  that produced it, from Lei n.º 7/2009 to Retificação n.º 13/2023.
- Every article shows "Contém as alterações dos seguintes diplomas" and links to each earlier
  version: `lei_busca_art_velho.php?nid=1047&artigonum=1047A0003&n_versao=1`.
- No `robots.txt` (404) and no terms of use or legal notice found on the site.

Two limits of the PGDL labels: they give each amending diploma's publication date, not the date
it entered into force; and the PGDL may lag behind the DR for recent amendments. The per-article
history is more current than the whole-code version list: the list stops at Retificação
n.º 13/2023, but the articles already include Lei n.º 32/2025 (which added article 252.º-B).

Other sources checked and set aside: the ACT's consolidated PDF of the code (current text only,
no history) and dre.tretas.org (mirrors the published diplomas, not consolidated text).

On reuse: Lei n.º 26/2016 allows reusing documents made available online without authorisation
unless stated otherwise, and legislative texts are not protected by copyright. Both are to be
confirmed before the dataset is published (Phase 6), not before fetching.

**Update, same day.** Rendered once with Playwright, the DR's consolidated page for the code
(`/dr/legislacao-consolidada/lei/2009-34546475`) carries the full current text and, under each
article, notes such as "Alterado pelo/a Artigo 2.º do/a Lei n.º 23/2012 - Diário da República
n.º 121/2012, Série I de 2012-06-25, em vigor a partir de 2012-08-01". That page has the same 601
articles as the PGDL and 331 such notes (288 "Alterado", 35 "Aditado", 8 "Retificado"): the
entry-into-force date of every change, per article, from the official source. Its list of
amending acts ends at Lei n.º 32/2025, the same as the PGDL, and the "Trabalho XXI" reform was
rejected by Parliament on 2026-06-19, so both sources are current as of this ADR.

The page's own list of amending acts also includes two Constitutional Court rulings
(Acórdãos n.º 338/2010 and n.º 602/2013), a temporary regime (Lei n.º 11/2013) and an Azores
regional decree. The PGDL shows none of them as versions. Acórdão n.º 602/2013 voided parts of the
2012 wording of article 368.º, among others, between its publication and Lei n.º 27/2014; neither
source records that as a separate version of the article text.

The page also contains the articles of Lei n.º 7/2009 itself (the law approving the code), whose
numbers 1.º to 14.º collide with the code's; the parser keeps them apart.

## Decision

- Fetch the consolidated text and each article's history from the PGDL, using the per-article
  history rather than the whole-code version list, and following the rules in
  CLAUDE.md (one request at a time, at least 1 s apart, descriptive User-Agent, raw cache).
- Take `valid_from` from the DR's per-article notes ("em vigor a partir de"), matched to the PGDL
  version introduced by the same diploma. The DR consolidated page is rendered with Playwright
  once and cached; it is never bulk-fetched.
- Verify automatically, for every article, that the PGDL and the DR name the same amending
  diplomas, and that the PGDL's current text matches the DR's. Every mismatch is logged and the DR
  wins. On top of that, spot-check 20 random older versions (Phase 1 exit criterion). This
  was automated against the DR's 'Versão à data de' view rather than done by hand; see
  `docs/checks/phase1-spot-check.md`.
- Constitutional Court rulings are not modelled as versions. Articles they touched (starting with
  368.º for 2013 to 2014) are excluded from `temporal` items over the affected periods.
- Every stored version keeps both its PGDL URL (where we read it) and the DR link to the diploma
  that introduced it (what we cite).

## Consequences

- Temporal questions are feasible: each article's history is explicit, not reconstructed.
- Around 600 current articles plus their earlier versions: roughly a thousand requests, about 20
  minutes at our rate, once, then from cache.
- The PGDL is a secondary source. Discrepancies with the DR found in spot checks are logged, and
  the DR wins. If the PGDL turns out to be missing amendments, the missing versions are entered
  from the DR by hand, or the affected articles are excluded from temporal items.
- If the PGDL changes its markup or goes away, the raw cache still rebuilds the store.
