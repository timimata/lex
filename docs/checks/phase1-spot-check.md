# Spot check of the Código do Trabalho: 20 earlier article versions

Produced by `python -m lex.ingest spot-check 20 --seed 2026 --code ct`:
every one of the 18 versions the build dated by a rule rather than the DR's note
(a correction, a date read from the diploma, a rectification's, a date the DR gives on
every other article), the riskiest, and 20 versions drawn at random from the
281 other earlier (no longer in force) versions in the store, each checked
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

**Result: differs 1, differs, a rectification's version 8, next version, same 1, same 54, spelling only 1** (65 checks).

| Article | DR as of | DR states in force | Store version | Result |
|---|---|---|---|---|
| 1 | 2009-02-17 | not stated | 2009-02-17 to in force | same |
| 106 | 2009-02-17 | not stated | 2009-02-17 to 2011-11-01 | same |
| 106 | 2011-10-31 | 2011-11-01 to 2012-07-31 | 2011-11-01 to 2012-08-01 | same |
| 12 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 12 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 129 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 129 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 189 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 189 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 208 | 2009-02-17 | not stated | 2009-02-17 to 2012-08-01 | same |
| 208 | 2012-07-31 | 2012-08-01 to in force | 2012-08-01 to in force | same |
| 375 | 2009-02-17 | not stated | 2009-02-17 to 2012-08-01 | same |
| 375 | 2012-07-31 | 2012-08-01 to 2014-05-31 | 2012-08-01 to 2014-06-01 | same |
| 384 | 2009-02-17 | not stated | 2009-02-17 to 2011-11-01 | same |
| 384 | 2011-10-31 | 2011-11-01 to 2012-07-31 | 2011-11-01 to 2012-08-01 | same |
| 394 | 2009-02-17 | not stated | 2009-02-17 to 2017-10-01 | same |
| 394 | 2017-09-30 | 2017-10-01 to 2018-03-19 | 2017-10-01 to 2018-03-20 | same |
| 485 | 2009-02-17 | not stated | 2009-02-17 to 2023-05-01 | same |
| 485 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 563 | 2009-02-17 | not stated | 2009-02-17 to 2017-10-01 | same |
| 563 | 2017-09-30 | 2017-10-01 to in force | 2017-10-01 to in force | differs, a rectification's version |
| 192 | 2012-08-01 | not stated | 2012-08-01 to 2013-10-01 | same |
| 192 | 2013-09-30 | 2013-10-01 to 2023-04-30 | 2013-10-01 to 2023-05-01 | same |
| 127 | 2013-10-01 | not stated | 2013-10-01 to 2015-09-06 | same |
| 127 | 2015-09-05 | 2015-09-06 to 2017-09-30 | 2015-09-06 to 2017-10-01 | differs |
| 501 | 2014-09-01 | not stated | 2014-09-01 to 2019-10-01 | same |
| 501 | 2019-09-30 | 2019-10-01 to 2023-04-03 | 2019-10-01 to 2023-04-04 | same |
| 43 | 2015-09-06 | not stated | 2015-09-06 to 2020-04-01 | same |
| 43 | 2020-03-31 | not stated | 2020-04-01 to 2023-05-01 | next version, same |
| 563 | 2017-10-01 | not stated | 2017-10-01 to in force | differs, a rectification's version |
| 285 | 2018-03-20 | not stated | 2018-03-20 to 2021-04-09 | same |
| 285 | 2021-04-08 | 2021-04-09 to 2023-04-30 | 2021-04-09 to 2023-05-01 | same |
| 286 | 2018-03-20 | not stated | 2018-03-20 to 2021-04-09 | same |
| 286 | 2021-04-08 | 2021-04-09 to in force | 2021-04-09 to in force | same |
| 112 | 2019-10-01 | not stated | 2019-10-01 to 2023-05-01 | same |
| 112 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | differs, a rectification's version |
| 3 | 2019-10-01 | not stated | 2019-10-01 to 2022-01-01 | same |
| 3 | 2021-12-31 | 2022-01-01 to 2023-04-30 | 2022-01-01 to 2023-05-01 | same |
| 497 | 2019-10-01 | not stated | 2019-10-01 to 2023-05-01 | same |
| 497 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 114 | 2019-10-04 | not stated | 2019-10-04 to 2023-05-01 | same |
| 114 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 252-A | 2019-10-04 | not stated | 2019-10-04 to 2023-05-01 | same |
| 252-A | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 255 | 2019-10-04 | not stated | 2019-10-04 to 2023-05-01 | same |
| 255 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 33-A | 2019-10-04 | not stated | 2019-10-04 to in force | same |
| 35 | 2020-04-01 | not stated | 2020-04-01 to 2023-05-01 | spelling only |
| 35 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 37-A | 2020-04-01 | not stated | 2020-04-01 to in force | same |
| 40 | 2020-04-01 | not stated | 2020-04-01 to 2023-05-01 | same |
| 40 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 42 | 2020-04-01 | not stated | 2020-04-01 to 2023-05-01 | same |
| 42 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 43 | 2020-04-01 | not stated | 2020-04-01 to 2023-05-01 | same |
| 43 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 53 | 2020-04-01 | not stated | 2020-04-01 to in force | same |
| 65 | 2020-04-01 | not stated | 2020-04-01 to 2023-05-01 | same |
| 65 | 2023-04-30 | 2023-05-01 to in force | 2023-05-01 to in force | same |
| 94 | 2020-04-01 | not stated | 2020-04-01 to in force | same |
| 112 | 2023-05-01 | not stated | 2023-05-01 to in force | differs, a rectification's version |
| 12-A | 2023-05-01 | not stated | 2023-05-01 to in force | differs, a rectification's version |
| 168 | 2023-05-01 | not stated | 2023-05-01 to in force | differs, a rectification's version |
| 251 | 2023-05-01 | not stated | 2023-05-01 to in force | differs, a rectification's version |
| 466 | 2023-05-01 | not stated | 2023-05-01 to in force | differs, a rectification's version |

## Differences

### 563, DR as of 2017-09-30: differs, a rectification's version

```diff
--- store
+++ DR
@@ -3 +3 @@
-3 - O disposto no n.º 1 não se aplica no caso de contraordenação a que se refere o n.º 5 do artigo 29.º.
+3 - O disposto no n.º 1 não se aplica no caso de contraordenação a que se refere o n.º 4 do artigo 29.º.
```

### 127, DR as of 2015-09-05: differs

```diff
--- store
+++ DR
@@ -15,3 +15,3 @@
-5 - O empregador deve comunicar ao serviço com competência inspetiva do ministério responsável pela área laboral a adesão ao fundo de compensação do trabalho ou a mecanismo equivalente, previstos em legislação específica.
-6 - A alteração do elemento referido no número anterior deve ser comunicada no prazo de 30 dias.
-7 - Constitui contraordenação leve a violação do disposto na alínea j) do n.º 1 e nos n.os 5 e 6.
+5 - (Revogado).
+6 - O empregador deve comunicar ao serviço com competência inspetiva do ministério responsável pela área laboral a adesão ao fundo de compensação do trabalho ou a mecanismo equivalente, previstos em legislação específica.
+7 - A alteração do elemento referido no número anterior deve ser comunicada no prazo de 30 dias.
```

### 563, DR as of 2017-10-01: differs, a rectification's version

```diff
--- store
+++ DR
@@ -3 +3 @@
-3 - O disposto no n.º 1 não se aplica no caso de contraordenação a que se refere o n.º 5 do artigo 29.º.
+3 - O disposto no n.º 1 não se aplica no caso de contraordenação a que se refere o n.º 4 do artigo 29.º.
```

### 112, DR as of 2023-04-30: differs, a rectification's version

```diff
--- store
+++ DR
@@ -14 +14 @@
-6 - O período experimental é reduzido ou excluído consoante a duração do estágio profissional com avaliação positiva, para a mesma atividade e empregador diferente, tenha sido igual ou superior a 90 dias, nos últimos 12 meses.
+6 - O período experimental é reduzido consoante a duração do estágio profissional com avaliação positiva, para a mesma atividade e empregador diferente, tenha sido igual ou superior a 90 dias, nos últimos 12 meses.
```

### 35, DR as of 2020-04-01: spelling only

```diff
--- store
+++ DR
@@ -11 +11 @@
-j Dispensa para avaliação para adopção;
+j) Dispensa para avaliação para adopção;
```

### 112, DR as of 2023-05-01: differs, a rectification's version

```diff
--- store
+++ DR
@@ -14 +14 @@
-6 - O período experimental é reduzido ou excluído consoante a duração do estágio profissional com avaliação positiva, para a mesma atividade e empregador diferente, tenha sido igual ou superior a 90 dias, nos últimos 12 meses.
+6 - O período experimental é reduzido consoante a duração do estágio profissional com avaliação positiva, para a mesma atividade e empregador diferente, tenha sido igual ou superior a 90 dias, nos últimos 12 meses.
```

### 12-A, DR as of 2023-05-01: differs, a rectification's version

```diff
--- store
+++ DR
@@ -7 +7 @@
-f) Os equipamentos e instrumentos de trabalho utilizados pertencem à plataforma digital ou são por esta explorados através de contrato de locação.
+f) Os equipamentos e instrumentos de trabalho utilizados pertencem à plataforma digital ou são por estes explorados através de contrato de locação.
```

### 168, DR as of 2023-05-01: differs, a rectification's version

```diff
--- store
+++ DR
@@ -3 +3 @@
-3 - O contrato individual de trabalho e o instrumento de regulamentação coletiva de trabalho aplicável devem fixar na celebração do acordo para prestação de teletrabalho o valor da compensação devida ao trabalhador pelas despesas adicionais.
+3 - O contrato individual de trabalho e o contrato coletivo de trabalho devem fixar na celebração do acordo para prestação de teletrabalho o valor da compensação devida ao trabalhador pelas despesas adicionais.
```

### 251, DR as of 2023-05-01: differs, a rectification's version

```diff
--- store
+++ DR
@@ -5 +5 @@
-2 - Aplica-se o disposto na alínea a) do número anterior em caso de falecimento de pessoa que viva em união de facto ou economia comum com o trabalhador, nos termos previstos em legislação específica.
+2 - Aplica-se o disposto na alínea b) do número anterior em caso de falecimento de pessoa que viva em união de facto ou economia comum com o trabalhador, nos termos previstos em legislação específica.
```

### 466, DR as of 2023-05-01: differs, a rectification's version

```diff
--- store
+++ DR
@@ -5 +5 @@
-d) Parâmetros, critérios, regras e instruções em que se baseiam os algoritmos ou outros sistemas de inteligência artificial que afetam a tomada de decisões sobre o acesso e a manutenção do emprego, assim como condições de trabalho, incluindo a elaboração de perfis e o controlo da atividade profissional.
+d) Parâmetros, os critérios, as regras e as instruções em que se baseiam os algoritmos ou outros sistemas de inteligência artificial que afetam a tomada de decisões sobre o acesso e a manutenção do emprego, assim como condições de trabalho, incluindo a elaboração de perfis e o controlo da atividade profissional.
```
