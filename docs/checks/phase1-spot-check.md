# Phase 1 spot check: 20 earlier article versions

Produced by `python -m lex.ingest spot-check 20 --seed 2026`: 20 versions drawn at
random from the 288 earlier (no longer in force) versions in the store, each
checked against the DR's *Versão à data de* view on its first and its last day in force.
How the check works, and what it shares with the build, is in
`src/lex/ingest/spot_check.py`. It is automated rather than done by hand.

*DR states* is the period in force the DR gives for the version it shows (first to last
day). *Store version* is the version it was compared with (first day in force to first
day out of force). Texts are compared after collapsing whitespace, dashes and the ways
of writing '(Revogado.)'.

**Result: differs 2, same 38** (40 checks).

| Article | DR as of | DR states in force | Store version | Result |
|---|---|---|---|---|
| 108 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 108 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 12 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 12 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 190 | 2009-02-17 | not stated | 2009-02-17 to 2011-11-01 | same |
| 190 | 2011-10-31 | 2011-11-01 to 2013-09-30 | 2011-11-01 to 2013-10-01 | same |
| 194 | 2009-02-17 | not stated | 2009-02-17 to 2011-11-01 | same |
| 194 | 2011-10-31 | 2011-11-01 to 2012-07-31 | 2011-11-01 to 2012-08-01 | same |
| 250 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 250 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 277 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 277 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 370 | 2009-02-17 | not stated | 2009-02-17 to 2012-08-01 | same |
| 370 | 2012-07-31 | 2012-08-01 to 2019-09-30 | 2012-08-01 to 2019-10-01 | same |
| 377 | 2009-02-17 | not stated | 2009-02-17 to 2012-08-01 | same |
| 377 | 2012-07-31 | 2012-08-01 to in force | 2012-08-01 to in force | same |
| 456 | 2009-02-17 | not stated | 2009-02-17 to 2019-10-01 | same |
| 456 | 2019-09-30 | 2019-10-01 to in force | 2019-10-01 to in force | same |
| 482 | 2009-02-17 | not stated | 2009-02-17 to 2012-08-01 | same |
| 482 | 2012-07-31 | 2012-08-01 to in force | 2012-08-01 to in force | same |
| 538 | 2009-02-17 | not stated | 2009-02-17 to 2009-09-15 | same |
| 538 | 2009-09-14 | not stated | 2009-02-17 to 2009-09-15 | differs |
| 87 | 2009-02-17 | not stated | 2009-02-17 to 2019-10-01 | same |
| 87 | 2019-09-30 | 2019-10-01 to in force | 2019-10-01 to in force | same |
| 127 | 2011-11-01 | not stated | 2011-11-01 to 2012-08-01 | same |
| 127 | 2012-07-31 | 2012-08-01 to 2013-09-30 | 2012-08-01 to 2013-10-01 | same |
| 383 | 2011-11-01 | not stated | 2011-11-01 to 2012-08-01 | same |
| 383 | 2012-07-31 | 2012-08-01 to 2023-04-30 | 2012-08-01 to 2023-05-01 | same |
| 492 | 2012-08-01 | not stated | 2012-08-01 to 2022-01-01 | same |
| 492 | 2021-12-31 | 2022-01-01 to in force | 2022-01-01 to in force | same |
| 106 | 2013-10-01 | not stated | 2013-10-01 to 2023-05-01 | same |
| 106 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 112 | 2019-10-01 | not stated | 2019-10-01 to 2023-05-01 | same |
| 112 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | differs |
| 268 | 2019-10-01 | not stated | 2019-10-01 to 2023-05-01 | same |
| 268 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 3 | 2019-10-01 | not stated | 2019-10-01 to 2022-01-01 | same |
| 3 | 2021-12-31 | 2022-01-01 to 2023-04-30 | 2022-01-01 to 2023-05-01 | same |
| 513 | 2019-10-01 | not stated | 2019-10-01 to 2023-04-04 | same |
| 513 | 2023-04-03 | 2023-04-04 to in force | 2023-04-04 to in force | same |

## Differences

### 538, DR as of 2009-09-14: differs

```diff
--- store
+++ DR
@@ -6 +6 @@
-b) Tratando-se de serviço da administração directa ou indirecta do Estado, de serviços das autarquias locais ou empresa do sector empresarial do Estado, por tribunal arbitral, constituído nos termos de lei específica sobre arbitragem obrigatória.
+b) Tratando-se de empresa do sector empresarial do Estado, por tribunal arbitral, constituído nos termos de lei específica sobre arbitragem obrigatória.
```

### 112, DR as of 2023-04-30: differs

```diff
--- store
+++ DR
@@ -14 +14 @@
-6 - O período experimental é reduzido ou excluído consoante a duração do estágio profissional com avaliação positiva, para a mesma atividade e empregador diferente, tenha sido igual ou superior a 90 dias, nos últimos 12 meses.
+6 - O período experimental é reduzido consoante a duração do estágio profissional com avaliação positiva, para a mesma atividade e empregador diferente, tenha sido igual ou superior a 90 dias, nos últimos 12 meses.
```
