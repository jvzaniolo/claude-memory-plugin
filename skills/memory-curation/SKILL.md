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
milésimo dia, e nunca devem ser generalizadas ou rebaixadas por desuso. O gancho no índice é apenas um ponteiro: abra a fonte antes de aplicar a regra.
Uso baixo não justifica apagar ou generalizar essas memórias.

## Ordem de leitura

O `MEMORY.md` abre com um bloco numerado dizendo **quando** ler o quê — antes de agir, ao tocar
um assunto com dossiê, ao precisar de termo exato, antes de gravar. Não é decoração: escrever a
regra certa não basta se o modelo a lê tarde demais para agir sobre ela.

O bloco é roteador, não conteúdo: cada item aponta para um momento e uma ação, nunca carrega o
fato em si. Mantenha-o em quatro linhas ou menos — ele é carregado em toda sessão.

## Reincidência

Quando o usuário cobra de novo uma regra que já existe como `feedback`, o contador `recurrence`
sobe no frontmatter dela, e o número aparece na `description` e na linha do índice como
`RECORRENTE: Nx`. O campo é para a máquina, o texto é o que age — o `check.sh` acusa se os dois
divergirem.

O valor não é a contagem. `recurrence` alto marca a regra que está gravada e mesmo assim não
está pegando: ou o texto não diz o que fazer no instante em que importa, ou o gancho do índice
não é reconhecível a tempo. Ao subir o contador, reescreva o texto com essa pergunta — contador
que sobe sem o texto mudar só documenta a mesma falha outra vez.

Conta apenas cobrança do usuário. Ler a memória e obedecer não é reincidência, e os outros tipos
não têm contador.

## O índice e os dossiês

`MEMORY.md` é carregado em toda sessão e tem teto de **200 linhas / 25 KB** — o de bytes morde
primeiro. Uma linha por memória não escala.

Quando um assunto passa de meia dúzia de memórias, crie um **dossiê**: um arquivo que ganha a
linha do índice e que nomeia e resume cada membro por `[[link]]`, organizado por sub-tema e com
ordem de leitura. Os membros saem do índice e passam a ser alcançados pelo dossiê.

Marque o dossiê no frontmatter com `role: dossier` ao lado do `type`. Não é decoração: a
consolidação só promove memória que tenha um dossiê para onde ir, e sem essa marca o assunto
inteiro fica fora dela — em silêncio.

**Arquivo sem linha no `MEMORY.md` não é órfão** se um dossiê o cobre. Antes de criar linha para
um arquivo que parece faltar, procure quem já o referencia:

```bash
grep -rl "\[\[SLUG\]\]" <store>/*.md
```

Se um dossiê o cobre, atualize a linha do dossiê ou a frase daquele item dentro dele — nunca
crie linha nova no índice. A cadeia certa é `MEMORY.md → dossiê → arquivo`.

## Quando uma memória é superada

Memória errada é pior que memória ausente, e a obsolescência raramente se anuncia: o mundo muda
no código, e a memória continua afirmando o que era verdade. **Data não resolve** — o conflito
costuma estar dentro de um arquivo só, ou a informação que invalida está no corpo de outra
memória, onde quem abre a antiga nunca a vê.

Quando constatar que uma memória ficou para trás, marque **nela** (não só em quem a superou):

```markdown
metadata:
  superseded_by: [slug-de-quem-supera]
```

E abra o corpo dela com um aviso ao leitor, em citação:

```markdown
> **Superada por [[slug-de-quem-supera]]** (data): o que exatamente mudou, e o que da memória
> antiga continua valendo.
```

Os dois juntos, sempre: o campo é para a máquina, o aviso é para quem abre o arquivo pelo
wikilink e nunca veria o campo. Diga também **o que ainda vale** — uma memória superada em um
ponto costuma continuar correta no resto, e apagá-la perderia isso.

Não remova a memória superada. Ela vira o registro de por que se pensava aquilo, que é
justamente o que não se recupera investigando.

## O que nunca fazer

- **Apagar porque a tarefa acabou.** Concluir não apaga: o valor de uma memória de tarefa é o
  domínio que ela carrega — a fórmula, a regra de negócio, o número medido, a decisão e o porquê
  — e isso sobrevive à entrega. Preserve conteúdo superado com aviso e sucessor explícito.
- **Encurtar linha de assunto alheio no índice.** Sem o contexto que a produziu, reescrever
  destrói o detalhe que era o valor dela: um path, um número, um identificador.
- **Escrever wikilink de exemplo com colchetes duplos.** Um corretor automático não distingue
  exemplo em prosa de link real. Em prosa, use crase.
- **Gravar especulação.** Na dúvida entre uma hipótese não fechada e nada, grave nada.

## Higiene

Em uma sessão de manutenção, rode a verificação depois de edição em lote no índice ou nos
dossiês. No worker isolado, não execute comandos: o processo local faz essa validação após
a resposta estruturada.

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/check.sh"
```

Ela acusa linha de índice sem arquivo, arquivo inalcançável, `[[link]]` quebrado e memória sem
`type`. Link quebrado importa mais do que parece: com dossiês, ele é um caminho sem saída.
