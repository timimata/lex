# Spot check of the Código Civil: 12 earlier article versions

Produced by `python -m lex.ingest spot-check 12 --seed 2026 --code cc`: 12
versions drawn at random from the 53 earlier (no longer in force) versions in the store, each
checked against the DR's *Versão à data de* view on its first and its last day in force.
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

**Result: punctuation only 2, same 22** (24 checks).

| Article | DR as of | DR states in force | Store version | Result |
|---|---|---|---|---|
| 1052 | 1967-06-01 | not stated | 1967-06-01 to 1978-04-01 | same |
| 1052 | 1978-03-31 | 1978-04-01 to in force | 1978-04-01 to in force | same |
| 1048 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 1048 | 2012-11-11 | 2012-11-12 to in force | 2012-11-12 to in force | same |
| 1083 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 1083 | 2012-11-11 | 2012-11-12 to 2017-06-14 | 2012-11-12 to 2017-06-15 | punctuation only |
| 1087 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 1087 | 2012-11-11 | 2012-11-12 to in force | 2012-11-12 to in force | same |
| 1097 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 1097 | 2012-11-11 | 2012-11-12 to 2019-02-12 | 2012-11-12 to 2019-02-13 | same |
| 1100 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 1100 | 2012-11-11 | 2012-11-12 to in force | 2012-11-12 to in force | same |
| 1069 | 2012-11-12 | not stated | 2012-11-12 to 2019-02-13 | same |
| 1069 | 2019-02-12 | 2019-02-13 to in force | 2019-02-13 to in force | same |
| 1097 | 2012-11-12 | not stated | 2012-11-12 to 2019-02-13 | same |
| 1097 | 2019-02-12 | 2019-02-13 to in force | 2019-02-13 to in force | same |
| 1098 | 2012-11-12 | not stated | 2012-11-12 to 2019-02-13 | punctuation only |
| 1098 | 2019-02-12 | 2019-02-13 to in force | 2019-02-13 to in force | same |
| 1101 | 2012-11-12 | not stated | 2012-11-12 to 2019-02-13 | same |
| 1101 | 2019-02-12 | 2019-02-13 to in force | 2019-02-13 to in force | same |
| 1106 | 2012-11-12 | not stated | 2012-11-12 to 2019-02-13 | same |
| 1106 | 2019-02-12 | 2019-02-13 to in force | 2019-02-13 to in force | same |
| 1095 | 2019-02-13 | not stated | 2019-02-13 to 2024-01-01 | same |
| 1095 | 2023-12-31 | 2024-01-01 to in force | 2024-01-01 to in force | same |

## Differences

### 1083, DR as of 2012-11-11: punctuation only

```diff
--- store
+++ DR
@@ -2 +2 @@
-2 - É fundamento de resolução o incumprimento que, pela sua gravidade ou consequências, torne inexigível à outra parte a manutenção do arrendamento, designadamente quanto à resolução pelo senhorio:
+2 - É fundamento de resolução o incumprimento que, pela sua gravidade ou consequências, torne inexigível à outra parte a manutenção do arrendamento, designadamente, quanto à resolução pelo senhorio:
```

### 1098, DR as of 2012-11-12: punctuation only

```diff
--- store
+++ DR
@@ -12 +12 @@
-6 - A inobservância da antecedência prevista nos números anteriores não obsta à cessação do contrato mas obriga ao pagamento das rendas correspondentes ao período de pré-aviso em falta.
+6 - A inobservância da antecedência prevista nos números anteriores não obsta à cessação do contrato, mas obriga ao pagamento das rendas correspondentes ao período de pré-aviso em falta.
```
