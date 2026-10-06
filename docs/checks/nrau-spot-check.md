# Spot check of the NRAU: 12 earlier article versions

Produced by `python -m lex.ingest spot-check 12 --seed 2026 --code nrau`: 12
versions drawn at random from the 91 earlier (no longer in force) versions in the store, each
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

**Result: differs 2, next version, revoked on both 4, next version, same 1, next version, spelling only 1, punctuation only 2, same 12, spelling only 2** (24 checks).

| Article | DR as of | DR states in force | Store version | Result |
|---|---|---|---|---|
| 29 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 29 | 2012-11-11 | 2012-11-12 to 2015-01-17 | 2012-11-12 to 2015-01-18 | same |
| 40 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 40 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, revoked on both |
| 41 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 41 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, revoked on both |
| 47 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 47 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, revoked on both |
| 49 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 49 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, revoked on both |
| 51 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 51 | 2012-11-11 | not stated | 2012-11-12 to 2015-01-18 | next version, spelling only |
| 52 | 2006-06-27 | not stated | 2006-06-27 to 2012-11-12 | same |
| 52 | 2012-11-11 | not stated | 2012-11-12 to in force | next version, same |
| 15-B | 2012-11-12 | not stated | 2012-11-12 to 2015-01-18 | punctuation only |
| 15-B | 2015-01-17 | 2015-01-18 to 2023-10-06 | 2015-01-18 to 2023-10-07 | punctuation only |
| 15-C | 2012-11-12 | not stated | 2012-11-12 to 2015-01-18 | same |
| 15-C | 2015-01-17 | 2015-01-18 to 2023-10-06 | 2015-01-18 to 2023-10-07 | same |
| 54 | 2012-11-12 | not stated | 2012-11-12 to 2015-01-18 | same |
| 54 | 2015-01-17 | 2015-01-18 to 2017-06-14 | 2015-01-18 to 2017-06-15 | same |
| 15-N | 2015-01-18 | not stated | 2015-01-18 to 2023-10-07 | spelling only |
| 15-N | 2023-10-06 | ... to 2023-10-06 | 2015-01-18 to 2023-10-07 | spelling only |
| 35 | 2019-02-13 | not stated | 2019-02-13 to 2020-04-01 | differs |
| 35 | 2020-03-31 | 2020-04-01 to 2023-10-06 | 2020-04-01 to 2023-10-07 | differs |

## Differences

### 51, DR as of 2012-11-11: next version, spelling only

```diff
--- store
+++ DR
@@ -12 +12 @@
-5 - Para efeitos da presente lei, «microentidade» é a empresa que, independentemente da sua forma jurídica, não ultrapasse, à data do balanço, dois dos três limites seguintes:
+5 - Para efeitos da presente lei, 'microentidade' é a empresa que, independentemente da sua forma jurídica, não ultrapasse, à data do balanço, dois dos três limites seguintes:
```

### 15-B, DR as of 2012-11-12: punctuation only

```diff
--- store
+++ DR
@@ -19 +19 @@
-7 - Faltando, à data da apresentação do requerimento, menos de 30 dias para o termo do prazo de prescrição ou de caducidade, ou ocorrendo outra causa de urgência, deve o requerente apresentar documento comprovativo do pedido de apoio judiciário requerido, mas ainda não concedido.
+7 - Faltando, à data da apresentação do requerimento, menos de 30 dias para o termo do prazo de prescrição ou de caducidade, ou ocorrendo outra causa de urgência, deve o requerente apresentar documento comprovativo do pedido de apoio judiciário requerido mas ainda não concedido.
```

### 15-B, DR as of 2015-01-17: punctuation only

```diff
--- store
+++ DR
@@ -19 +19 @@
-7 - Faltando, à data da apresentação do requerimento, menos de 30 dias para o termo do prazo de prescrição ou de caducidade, ou ocorrendo outra causa de urgência, deve o requerente apresentar documento comprovativo do pedido de apoio judiciário requerido, mas ainda não concedido.
+7 - Faltando, à data da apresentação do requerimento, menos de 30 dias para o termo do prazo de prescrição ou de caducidade, ou ocorrendo outra causa de urgência, deve o requerente apresentar documento comprovativo do pedido de apoio judiciário requerido mas ainda não concedido.
```

### 15-N, DR as of 2015-01-18: spelling only

```diff
--- store
+++ DR
@@ -1,3 +1,3 @@
-1 - No caso de imóvel arrendado para habitação, dentro do prazo para a oposição ao procedimento especial de despejo, o arrendatário pode requerer ao juiz do tribunal judicial da situação do locado o diferimento da desocupação, por razões sociais imperiosas, devendo logo oferecer as provas disponíveis e indicar as testemunhas a apresentar, até ao limite de três.
-2 - O diferimento de desocupação do locado para habitação é decidido de acordo com o prudente arbítrio do tribunal, devendo o juiz ter em consideração as exigências da boa-fé, a circunstância de o arrendatário não dispor imediatamente de outra habitação, o número de pessoas que habitam com o arrendatário, a sua idade, o seu estado de saúde e, em geral, a situação económica e social das pessoas envolvidas, só podendo ser concedido desde que se verifique algum dos seguintes fundamentos:
-a) Que, tratando-se de resolução por não pagamento de rendas, a falta do mesmo se deve a carência de meios do arrendatário, o que se presume relativamente ao beneficiá-rio de subsídio de desemprego, de valor igual ou inferior à retribuição mínima mensal garantida, ou de rendimento social de inserção;
+1 - No caso de imóvel arrendado para habitação, dentro do prazo para a oposição ao procedimento especial de despejo, o arrendatário pode requerer ao juiz do tribunal judicial da situação do locado o diferimento da desocupação por razões sociais imperiosas, devendo logo oferecer as provas disponíveis e indicar as testemunhas a apresentar, até ao limite de três.
+2 - O diferimento de desocupação do locado para habitação é decidido de acordo com o prudente arbítrio do tribunal, devendo o juiz ter em consideração as exigências da boa fé, a circunstância de o arrendatário não dispor imediatamente de outra habitação, o número de pessoas que habitam com o arrendatário, a sua idade, o seu estado de saúde e, em geral, a situação económica e social das pessoas envolvidas, só podendo ser concedido desde que se verifique algum dos seguintes fundamentos:
+a) Que, tratando-se de resolução por não pagamento de rendas, a falta do mesmo se deve a carência de meios do arrendatário, o que se presume relativamente ao beneficiário de subsídio de desemprego, de valor igual ou inferior à retribuição mínima mensal garantida, ou de rendimento social de inserção;
```

### 15-N, DR as of 2023-10-06: spelling only

```diff
--- store
+++ DR
@@ -1,3 +1,3 @@
-1 - No caso de imóvel arrendado para habitação, dentro do prazo para a oposição ao procedimento especial de despejo, o arrendatário pode requerer ao juiz do tribunal judicial da situação do locado o diferimento da desocupação, por razões sociais imperiosas, devendo logo oferecer as provas disponíveis e indicar as testemunhas a apresentar, até ao limite de três.
-2 - O diferimento de desocupação do locado para habitação é decidido de acordo com o prudente arbítrio do tribunal, devendo o juiz ter em consideração as exigências da boa-fé, a circunstância de o arrendatário não dispor imediatamente de outra habitação, o número de pessoas que habitam com o arrendatário, a sua idade, o seu estado de saúde e, em geral, a situação económica e social das pessoas envolvidas, só podendo ser concedido desde que se verifique algum dos seguintes fundamentos:
-a) Que, tratando-se de resolução por não pagamento de rendas, a falta do mesmo se deve a carência de meios do arrendatário, o que se presume relativamente ao beneficiá-rio de subsídio de desemprego, de valor igual ou inferior à retribuição mínima mensal garantida, ou de rendimento social de inserção;
+1 - No caso de imóvel arrendado para habitação, dentro do prazo para a oposição ao procedimento especial de despejo, o arrendatário pode requerer ao juiz do tribunal judicial da situação do locado o diferimento da desocupação por razões sociais imperiosas, devendo logo oferecer as provas disponíveis e indicar as testemunhas a apresentar, até ao limite de três.
+2 - O diferimento de desocupação do locado para habitação é decidido de acordo com o prudente arbítrio do tribunal, devendo o juiz ter em consideração as exigências da boa fé, a circunstância de o arrendatário não dispor imediatamente de outra habitação, o número de pessoas que habitam com o arrendatário, a sua idade, o seu estado de saúde e, em geral, a situação económica e social das pessoas envolvidas, só podendo ser concedido desde que se verifique algum dos seguintes fundamentos:
+a) Que, tratando-se de resolução por não pagamento de rendas, a falta do mesmo se deve a carência de meios do arrendatário, o que se presume relativamente ao beneficiário de subsídio de desemprego, de valor igual ou inferior à retribuição mínima mensal garantida, ou de rendimento social de inserção;
```

### 35, DR as of 2019-02-13: differs

```diff
--- store
+++ DR
@@ -11 +10,0 @@
-d) O arrendatário pode requerer a reavaliação do locado, nos termos do Código do IMI.
@@ -14,2 +13,2 @@
-5 - Nos anos seguintes ao da invocação da circunstância regulada no presente artigo, o inquilino faz prova dessa circunstância, pela mesma forma e até ao dia 30 de setembro, quando essa prova seja exigida pelo senhorio até ao dia 1 de setembro do respetivo ano, sob pena de não poder prevalecer-se daquela circunstância.
-6 - Findo o prazo de oito anos referido no n.º 1, o senhorio pode promover a transição do contrato para o NRAU, aplicando-se, com as necessárias adaptações, o disposto nos artigos 30.º e seguintes, com as seguintes especificidades:
+5 - No mês correspondente àquele em que foi feita a invocação da circunstância regulada no presente artigo e pela mesma forma, o arrendatário faz prova anual do rendimento perante o senhorio, sob pena de não poder prevalecer-se da mesma.
+6 - Findo o prazo de oito anos referido no n.º 1, o senhorio pode promover a transição do contrato para o NRAU, aplicando-se, com as necessárias adaptações, o disposto nos artigos 30.º e seguintes, com as seguintes especificidades
```

### 35, DR as of 2020-03-31: differs

```diff
--- store
+++ DR
@@ -14 +14 @@
-5 - Nos anos seguintes ao da invocação da circunstância regulada no presente artigo, o inquilino faz prova dessa circunstância, pela mesma forma e até ao dia 30 de setembro, quando essa prova seja exigida pelo senhorio até ao dia 1 de setembro do respetivo ano, sob pena de não poder prevalecer-se daquela circunstância.
+5 - No mês correspondente àquele em que foi feita a invocação da circunstância regulada no presente artigo e pela mesma forma, o arrendatário faz prova anual do rendimento perante o senhorio, sob pena de não poder prevalecer-se da mesma.
```
