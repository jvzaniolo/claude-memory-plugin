---
name: memory-curation
description: Como curar o store de memória de longo prazo — o que grava e o que não grava, o formato de um arquivo-tópico, quando um assunto vira dossiê, e por que arquivo fora do índice não é defeito. Use ao escrever, reorganizar ou auditar memórias, e quando o índice MEMORY.md se aproximar do teto de 200 linhas / 25 KB.
---

# Curadoria da memória de longo prazo

## O princípio

A memória guarda **o que não se recupera investigando**. A verdade sobre o código vive no git,
no banco, no Slack, no Drive — e você a busca lá, do jeito normal, quando precisar. O que não
existe em nenhuma dessas fontes é o que merece um arquivo: por que uma decisão foi tomada, o que
foi tentado e descartado, quem é o cliente, uma regra que só apareceu numa conversa, um número
que só existiu naquela análise.

Antes de gravar, pergunte: **eu descobriria isso sozinho investigando?** Se sim, não grave.

## Formato

Um arquivo por ideia, em Markdown, com frontmatter:

```markdown
---
name: <slug-em-kebab-case>
description: <uma linha; é o que decide relevância no recall e no catálogo>
metadata:
  type: user | feedback | project | reference
---

<o fato. Para feedback e project, siga com **Why:** e **How to apply:**.>
Ligue memórias relacionadas com [[o-slug-da-outra]].
```

Os quatro tipos, e a diferença importa mais do que parece:

- **`user`** — quem é a pessoa: papel, expertise, preferências.
- **`feedback`** — como você deve trabalhar; correção ou abordagem confirmada. Inclua o porquê.
- **`project`** — trabalho em andamento, objetivo, restrição, estado de tarefa longa.
- **`reference`** — ponteiro para recurso externo, armadilha técnica reutilizável.

`feedback` e `reference` são **regras que não envelhecem**: valem igual no primeiro e no
milésimo dia, e nunca devem ser generalizadas ou rebaixadas por desuso. Elas costumam agir sem
que ninguém abra o arquivo — o gancho no índice basta —, então uso baixo não é sinal de pouco
valor. É o contrário.

## O índice e os dossiês

`MEMORY.md` é carregado em toda sessão e tem teto de **200 linhas / 25 KB** — o de bytes morde
primeiro. Uma linha por memória não escala.

Quando um assunto passa de meia dúzia de memórias, crie um **dossiê**: um arquivo que ganha a
linha do índice e que nomeia e resume cada membro por `[[link]]`, organizado por sub-tema e com
ordem de leitura. Os membros saem do índice e passam a ser alcançados pelo dossiê.

**Arquivo sem linha no `MEMORY.md` não é órfão** se um dossiê o cobre. Antes de criar linha para
um arquivo que parece faltar, procure quem já o referencia:

```bash
grep -rl "\[\[SLUG\]\]" <store>/*.md
```

Se um dossiê o cobre, atualize a linha do dossiê ou a frase daquele item dentro dele — nunca
crie linha nova no índice. A cadeia certa é `MEMORY.md → dossiê → arquivo`.

## O que nunca fazer

- **Apagar porque a tarefa acabou.** Concluir não apaga: o valor de uma memória de tarefa é o
  domínio que ela carrega — a fórmula, a regra de negócio, o número medido, a decisão e o porquê
  — e isso sobrevive à entrega. Remova só o que se provou errado ou vencido.
- **Encurtar linha de assunto alheio no índice.** Sem o contexto que a produziu, reescrever
  destrói o detalhe que era o valor dela: um path, um número, um identificador.
- **Escrever wikilink de exemplo com colchetes duplos.** Um corretor automático não distingue
  exemplo em prosa de link real. Em prosa, use crase.
- **Gravar especulação.** Na dúvida entre uma hipótese não fechada e nada, grave nada.

## Higiene

Rode a verificação depois de qualquer edição em lote no índice ou nos dossiês:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/check.sh"
```

Ela acusa linha de índice sem arquivo, arquivo inalcançável, `[[link]]` quebrado e memória sem
`type`. Link quebrado importa mais do que parece: com dossiês, ele é um caminho sem saída.
