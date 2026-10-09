# Spot check of the NRAU: 12 earlier article versions

Produced by `python -m lex.ingest spot-check 12 --seed 2026 --code nrau`:
every one of the 17 versions the build dated by a rule rather than the DR's note
(a correction, a date read from the diploma, a rectification's, a date the DR gives on
every other article), the riskiest, and 12 versions drawn at random from the
90 other earlier (no longer in force) versions in the store, each checked
against the DR's *Versão à data de* view on its first and, if it has one, its last day in force.
How the check works, and what it shares with the build, is in
`src/lex/ingest/spot_check.py`. It is automated rather than done by hand.

*DR states* is the period in force the DR gives for the version it shows (first to last
day). *Store version* is the version it was compared with (first day in force to first
day out of force). Texts are compared after collapsing whitespace, dashes and the ways
of writing '(Revogado.)'. *Punctuation only* and *spelling only* (the same letters and
digits once the 1990 agreement's silent consonants are dropped, as in a republished
text) are listed apart. *Next version* means the DR showed, on a version's last day,
the next one, published but not yet in force, without stating its period; it was then
compared with the store's next version.

**Result: dates differ, corrected in codes.py 1, differs 1, next version, punctuation only 1, next version, revoked on both 3, next version, same 1, punctuation only 1, revoked on both 14, same 19, spelling only 1** (42 checks).

| Article | DR as of | DR states in force | Store version | Result |
|---|---|---|---|---|
| 63 | 2006-02-28 | not stated | 2006-02-28 to in force | same |
| 64 | 2006-02-28 | not stated | 2006-02-28 to in force | same |
| 12 | 2006-06-27 | 2006-06-28 to 2017-06-14 | 2006-06-27 to 2017-06-15 | dates differ, corrected in codes.py |
| 12 | 2017-06-14 | 2017-06-15 to in force | 2017-06-15 to in force | same |
| 41 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 41 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, revoked on both |
| 42 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 42 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, revoked on both |
| 48 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 48 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, revoked on both |
| 50 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 50 | 2012-11-11 | not stated | 2012-11-12 to 2015-01-18 | next version, punctuation only |
| 53 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 53 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, same |
| 15-O | 2012-11-12 | not stated | 2012-11-12 to 2023-10-07 | same |
| 15-O | 2023-10-06 | ... to 2023-10-06 | 2012-11-12 to 2023-10-07 | same |
| 29 | 2012-11-12 | not stated | 2012-11-12 to 2015-01-18 | same |
| 29 | 2015-01-17 | 2015-01-18 to in force | 2015-01-18 to in force | same |
| 38 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 39 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 40 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 41 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 42 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 43 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 44 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 45 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 46 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 47 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 48 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 49 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 51 | 2012-11-12 | not stated | 2012-11-12 to 2015-01-18 | spelling only |
| 51 | 2015-01-17 | 2015-01-18 to 2017-06-23 | 2015-01-18 to 2017-06-24 | same |
| 55 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 56 | 2012-11-12 | not stated | 2012-11-12 to in force | revoked on both |
| 15-B | 2015-01-18 | not stated | 2015-01-18 to 2023-10-07 | punctuation only |
| 15-B | 2023-10-06 | 2023-10-07 to in force | 2023-10-07 to in force | same |
| 15-C | 2015-01-18 | not stated | 2015-01-18 to 2023-10-07 | same |
| 15-C | 2023-10-06 | 2023-10-07 to in force | 2023-10-07 to in force | same |
| 54 | 2015-01-18 | not stated | 2015-01-18 to 2017-06-15 | same |
| 54 | 2017-06-14 | 2017-06-15 to in force | 2017-06-15 to in force | same |
| 35 | 2020-04-01 | not stated | 2020-04-01 to 2023-10-07 | differs |
| 35 | 2023-10-06 | 2023-10-07 to in force | 2023-10-07 to in force | same |

## Differences

### 50, DR as of 2012-11-11: next version, punctuation only

```diff
--- store
+++ DR
@@ -3 +3 @@
-b) O valor do locado, avaliado nos termos dos artigos 38.º e seguintes do CIMI, constante da caderneta predial urbana;
+b) O valor do locado, avaliado nos termos dos artigos 38.º e seguintes do CIMI constante da caderneta predial urbana;
```

### 51, DR as of 2012-11-12: spelling only

```diff
--- store
+++ DR
@@ -12 +12 @@
-5 - Para efeitos da presente lei, «microentidade» é a empresa que, independentemente da sua forma jurídica, não ultrapasse, à data do balanço, dois dos três limites seguintes:
+5 - Para efeitos da presente lei, 'microentidade' é a empresa que, independentemente da sua forma jurídica, não ultrapasse, à data do balanço, dois dos três limites seguintes:
```

### 15-B, DR as of 2015-01-18: punctuation only

```diff
--- store
+++ DR
@@ -19 +19 @@
-7 - Faltando, à data da apresentação do requerimento, menos de 30 dias para o termo do prazo de prescrição ou de caducidade, ou ocorrendo outra causa de urgência, deve o requerente apresentar documento comprovativo do pedido de apoio judiciário requerido, mas ainda não concedido.
+7 - Faltando, à data da apresentação do requerimento, menos de 30 dias para o termo do prazo de prescrição ou de caducidade, ou ocorrendo outra causa de urgência, deve o requerente apresentar documento comprovativo do pedido de apoio judiciário requerido mas ainda não concedido.
```

### 35, DR as of 2020-04-01: differs

```diff
--- store
+++ DR
@@ -14 +14 @@
-5 - Nos anos seguintes ao da invocação da circunstância regulada no presente artigo, o inquilino faz prova dessa circunstância, pela mesma forma e até ao dia 30 de setembro, quando essa prova seja exigida pelo senhorio até ao dia 1 de setembro do respetivo ano, sob pena de não poder prevalecer-se daquela circunstância.
+5 - No mês correspondente àquele em que foi feita a invocação da circunstância regulada no presente artigo e pela mesma forma, o arrendatário faz prova anual do rendimento perante o senhorio, sob pena de não poder prevalecer-se da mesma.
```
