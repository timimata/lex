# Batch 01: 10 items, drafted and reviewed

Drafted from two ACT sources on 2026-09-29 and checked against the text in force that day
in the store. Reviewed by the same model that drafted them (`reviewed_by:
claude-opus-5.5`), at Tiago's request: a second, adversarial pass over each source and
article, not an independent review. All 10 approved, one question reworded, one note
extended. They went into `bench/data/incoming.jsonl` and were assigned to dev or test by
`python -m lex.bench assign`. None is legally validated yet (`status: draft`).

## ct-0001

- [x] **Aprovado.** Assigned to test: its content lives only in `bench/data/test.jsonl`, so it is not repeated here.

## ct-0002

- [x] **Aprovado.** Assigned to test: its content lives only in `bench/data/test.jsonl`, so it is not repeated here.

## ct-0003

- [x] **Aprovado.** Assigned to test: its content lives only in `bench/data/test.jsonl`, so it is not repeated here.

## ct-0004 · composite

- [x] **Aprovado.** Correto: art. 244.º, n.os 1 e 2, com o 251.º. A inclusão do falecimento em 'outro facto que não lhe seja imputável' é da ACT, e está nas notas.

**Pergunta:** Se o pai de um trabalhador morrer enquanto ele está de férias, as férias ficam suspensas?

**Resposta:** Sim, segundo a ACT. O falecimento é um facto não imputável ao trabalhador que o impede de gozar as férias, pelo que o gozo se suspende (art. 244.º, n.º 1), desde que o comunique ao empregador. A ausência rege-se pelo regime das faltas por falecimento (art. 251.º) e os dias de férias por gozar são marcados depois (art. 244.º, n.º 2).

**Artigos:** 244, 251, (249), (253), (254)  (entre parênteses: podem ser citados, não são obrigatórios)

**Fonte:** [ACT, Nota Técnica n.º 7 - Faltas por motivo de falecimento de familiar (atualizada a 18/12/2023)](https://portal.act.gov.pt/AnexosPDF/Notas%20t%C3%A9cnicas/7%20Nota%20T%C3%A9cnica%20-%20resumo%20Faltas%20por%20motivo%20de%20falecimento%20de%20familiar.pdf)

> O falecimento de familiar adia ou suspende o gozo das férias, na medida em que não depende da vontade do trabalhador e impossibilita o gozo do direito a férias que visa o descanso e recuperação física do trabalhador.

**Notas:** A lei diz 'doença ou outro facto que não lhe seja imputável'; incluir o falecimento de familiar nesse conceito é a interpretação da ACT, apoiada em doutrina.

<details><summary>Art. 244.º em vigor hoje</summary>

> 1 - O gozo das férias não se inicia ou suspende-se quando o trabalhador esteja temporariamente impedido por doença ou outro facto que não lhe seja imputável, desde que haja comunicação do mesmo ao empregador.
> 2 - Em caso referido no número anterior, o gozo das férias tem lugar após o termo do impedimento na medida do remanescente do período marcado, devendo o período correspondente aos dias não gozados ser marcado por acordo ou, na falta deste, pelo empregador, sem sujeição ao disposto no n.º 3 do artigo 241.º
> 3 - Em caso de impossibilidade total ou parcial do gozo de férias por motivo de impedimento do trabalhador, este tem direito à retribuição correspondente ao período de férias não gozado ou ao gozo do mesmo até 30 de Abril do ano seguinte e, em qualquer caso, ao respectivo subsídio.
> 4 - À doença do trabalhador no período de férias é aplicável o disposto nos n.os 2 e 3 do artigo 254.º
> 5 - O disposto no n.º 1 não se aplica caso o trabalhador se oponha à verificação da situação de doença nos termos do artigo 254.º
> 6 - Constitui contra-ordenação grave a violação do disposto nos n.os 1, 2 ou 3.

</details>

<details><summary>Art. 251.º em vigor hoje</summary>

> 1 - O trabalhador pode faltar justificadamente:
> a) Até 20 dias consecutivos, por falecimento de cônjuge não separado de pessoas e bens ou equiparado, filho ou enteado;
> b) Até cinco dias consecutivos, por falecimento de parente ou afim no 1.º grau na linha reta não incluídos na alínea anterior;
> c) Até dois dias consecutivos, por falecimento de outro parente ou afim na linha recta ou no 2.º grau da linha colateral.
> 2 - Aplica-se o disposto na alínea a) do número anterior em caso de falecimento de pessoa que viva em união de facto ou economia comum com o trabalhador, nos termos previstos em legislação específica.
> 3 - Constitui contra-ordenação grave a violação do disposto neste artigo.

</details>

## ct-0005 · explicit_reference

- [x] **Aprovado.** Correto: paráfrase fiel do art. 244.º, n.º 1.

**Pergunta:** O que estabelece o n.º 1 do artigo 244.º do Código do Trabalho?

**Resposta:** Que o gozo das férias não se inicia, ou suspende-se, quando o trabalhador esteja temporariamente impedido por doença ou outro facto que não lhe seja imputável, desde que comunique a situação ao empregador.

**Artigos:** 244

**Fonte:** [ACT, Nota Técnica n.º 7 - Faltas por motivo de falecimento de familiar (atualizada a 18/12/2023)](https://portal.act.gov.pt/AnexosPDF/Notas%20t%C3%A9cnicas/7%20Nota%20T%C3%A9cnica%20-%20resumo%20Faltas%20por%20motivo%20de%20falecimento%20de%20familiar.pdf)

> Reza o artigo 244.º, n.º 1 do CT que o gozo de férias não se inicia ou suspende-se quando o trabalhador esteja temporariamente impedido por doença ou outro facto que não lhe seja imputável, desde que haja comunicação do mesmo ao empregador

<details><summary>Art. 244.º em vigor hoje</summary>

> 1 - O gozo das férias não se inicia ou suspende-se quando o trabalhador esteja temporariamente impedido por doença ou outro facto que não lhe seja imputável, desde que haja comunicação do mesmo ao empregador.
> 2 - Em caso referido no número anterior, o gozo das férias tem lugar após o termo do impedimento na medida do remanescente do período marcado, devendo o período correspondente aos dias não gozados ser marcado por acordo ou, na falta deste, pelo empregador, sem sujeição ao disposto no n.º 3 do artigo 241.º
> 3 - Em caso de impossibilidade total ou parcial do gozo de férias por motivo de impedimento do trabalhador, este tem direito à retribuição correspondente ao período de férias não gozado ou ao gozo do mesmo até 30 de Abril do ano seguinte e, em qualquer caso, ao respectivo subsídio.
> 4 - À doença do trabalhador no período de férias é aplicável o disposto nos n.os 2 e 3 do artigo 254.º
> 5 - O disposto no n.º 1 não se aplica caso o trabalhador se oponha à verificação da situação de doença nos termos do artigo 254.º
> 6 - Constitui contra-ordenação grave a violação do disposto nos n.os 1, 2 ou 3.

</details>

## ct-0006 · simple

- [x] **Aprovado.** Correto: art. 263.º, n.º 1.

**Pergunta:** Até quando tem de ser pago o subsídio de Natal?

**Resposta:** Até 15 de dezembro de cada ano. O valor é igual a um mês de retribuição.

**Artigos:** 263

**Fonte:** [ACT, Trabalhar em Portugal (guia para o trabalhador estrangeiro, 2026)](https://portal.act.gov.pt/AnexosPDF/Documenta%C3%A7%C3%A3o/Brochuras,%20folhetos%20e%20cartazes/Folhetos/Rela%C3%A7%C3%B5es%20de%20Trabalho/guia_trabalhadorestrangeiro_PT.pdf)

> O subsídio de Natal (igual ao ordenado) é pago até 15 de dezembro

<details><summary>Art. 263.º em vigor hoje</summary>

> 1 - O trabalhador tem direito a subsídio de Natal de valor igual a um mês de retribuição, que deve ser pago até 15 de Dezembro de cada ano.
> 2 - O valor do subsídio de Natal é proporcional ao tempo de serviço prestado no ano civil, nas seguintes situações:
> a) No ano de admissão do trabalhador;
> b) No ano de cessação do contrato de trabalho;
> c) Em caso de suspensão de contrato de trabalho por facto respeitante ao trabalhador.
> 3 - Constitui contra-ordenação muito grave a violação do disposto neste artigo.

</details>

## ct-0007

- [x] **Aprovado.** Assigned to test: its content lives only in `bench/data/test.jsonl`, so it is not repeated here.

## ct-0008

- [x] **Aprovado.** First assigned to test, moved to dev when splits became grouped by main article (ADR 0009); its content is in `bench/data/dev.jsonl`.

## ct-0009 · unanswerable

- [x] **Aprovado.** Correto: o art. 273.º remete o valor para legislação específica. As Regiões Autónomas têm valores próprios, o que não muda a resposta.

**Pergunta:** Qual é o valor do salário mínimo nacional em 2026?

**Resposta:** O Código do Trabalho não fixa esse valor: garante uma retribuição mínima mensal cujo valor é determinado anualmente por legislação específica (art. 273.º, n.º 1). A resposta certa é dizer que o valor não consta do Código.

**Artigos:** nenhum (deve recusar)

**Fonte:** [ACT, Trabalhar em Portugal (guia para o trabalhador estrangeiro, 2026)](https://portal.act.gov.pt/AnexosPDF/Documenta%C3%A7%C3%A3o/Brochuras,%20folhetos%20e%20cartazes/Folhetos/Rela%C3%A7%C3%B5es%20de%20Trabalho/guia_trabalhadorestrangeiro_PT.pdf)

> O salário mínimo é de 920 euros (brutos) por mês para trabalho a tempo inteiro

**Notas:** A fonte indica 920 euros brutos por mês em 2026. Citar o art. 273.º ao recusar é correto.

## ct-0010 · unanswerable

- [x] **Aprovado.** Correto: confirmado que o Código não tem a regra (só o art. 72.º, para menores) e que está no art. 108.º da Lei n.º 102/2009. Acrescentada a fonte nas notas.

**Pergunta:** Com que periodicidade deve um trabalhador com mais de 50 anos fazer exames de saúde periódicos?

**Resposta:** O Código do Trabalho não regula essa periodicidade; está no regime jurídico da promoção da segurança e saúde no trabalho, fora deste corpus. A resposta certa é dizer que não consta do Código.

**Artigos:** nenhum (deve recusar)

**Fonte:** [ACT, Trabalhar em Portugal (guia para o trabalhador estrangeiro, 2026)](https://portal.act.gov.pt/AnexosPDF/Documenta%C3%A7%C3%A3o/Brochuras,%20folhetos%20e%20cartazes/Folhetos/Rela%C3%A7%C3%B5es%20de%20Trabalho/guia_trabalhadorestrangeiro_PT.pdf)

> exames periódicos - feitos de 2 em 2 anos (ou anualmente para trabalhadores com mais de 50 anos)

**Notas:** A regra está no art. 108.º da Lei n.º 102/2009: exames anuais para menores e para quem tem mais de 50 anos, de 2 em 2 anos para os restantes, podendo o médico do trabalho alterar a periodicidade. Armadilha: o art. 72.º do Código prevê exame anual, mas só para menores.
