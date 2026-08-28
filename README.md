# claude-memory

Memória de longo prazo curada para o Claude Code — que **envelhece como memória humana**: o
recente fica detalhado, o antigo e pouco usado passa a ser lembrado pelo essencial, e nada é
apagado.

Construído em cima do auto-memory nativo do Claude Code, não no lugar dele.

## O problema

O auto-memory nativo já grava notas em Markdown e as recupera por relevância. Três coisas o
limitam na prática:

1. **É por repositório.** Trabalho num monorepo, em submódulos ou em vários repos não se
   enxerga. É fácil acabar com pools de memória espalhados que nunca mais são carregados.
2. **O índice tem teto** — 200 linhas / 25 KB, e o de bytes morde primeiro. Uma linha por
   memória satura em algumas centenas.
3. **Nada envelhece.** Uma anotação de tarefa de seis meses atrás ocupa o mesmo espaço, com o
   mesmo detalhe, que a de ontem.

E há um quarto, que não é do auto-memory mas muda tudo: **o Claude Code apaga transcripts de
sessão com mais de 30 dias, em silêncio, por padrão**. Quem trata o histórico como acervo
descobre tarde.

## O que este plugin adiciona

| peça | o que faz |
|---|---|
| **hook `Stop`** | a cada ~120 eventos de transcript, dispara um worker headless que retoma a própria sessão (`--resume --fork-session`, contexto integral), grava as conclusões duráveis e sai. Não bloqueia sua thread. |
| **`/memory-setup`** | configura pool único, retenção de transcript e a consolidação diária — conversando, com backup e confirmação a cada passo. |
| **`/memory-find`** | busca em duas camadas: `grep` para termo exato, catálogo completo para escolher por sentido. |
| **consolidação diária** | memória de tarefa fria (>30 dias) e pouco usada tem a essência promovida ao dossiê do assunto. O arquivo detalhado permanece. |
| **skill `memory-curation`** | o que grava, o que não grava, quando um assunto vira dossiê. |
| **`check.sh`** | integridade: link quebrado, arquivo inalcançável, linha de índice sem arquivo. |

## Ideias que sustentam o desenho

**A memória guarda o que não se recupera investigando.** O código está no git, o dado está no
banco, a conversa está no Slack. Antes de gravar: *eu descobriria isso sozinho investigando?* Se
sim, não grave. Esquecer o que é recuperável é saudável — quando precisar, procura-se.

**Dossiês em vez de índice plano.** Um assunto grande ganha um arquivo-índice que nomeia e
resume seus membros; os membros saem do `MEMORY.md`. A cadeia vira `índice → dossiê → arquivo`,
e o teto deixa de morder. Arquivo fora do índice não é órfão quando um dossiê o cobre.

**Concluir não apaga.** O valor de uma memória de tarefa é o domínio que ela carrega — a regra
de negócio, o número medido, o porquê da decisão. Isso sobrevive à entrega. Só sai o que se
provou errado.

**Regra de comportamento não envelhece.** Memórias `feedback` e `reference` ficam fora da
consolidação. Elas costumam agir sem que ninguém abra o arquivo, então uso baixo não é sinal de
pouco valor — é o contrário, e um sistema que rebaixasse por desuso apagaria primeiro o que mais
importa.

**Acesso promove, desuso não condena.** O worker conta uso real; o contador protege da
consolidação, dentro de uma janela de 90 dias. O total histórico nunca decresce, mas deixa de
escudar quando o assunto esfria de vez.

**Busca é ler, não indexar.** Em um store de centenas de memórias, o catálogo com todas as
descrições cabe em ~1% de um contexto de 1M. Índice vetorial existe para corpus que não cabe;
este cabe — e ler entende negação e nuance, que similaridade de vetor não distingue.

## Instalação

```bash
/plugin marketplace add <url-deste-repo>
/plugin install memory
/memory-setup
```

Depois de instalar, **reinicie a sessão**: `autoMemoryDirectory` só é lido no início.

Requisitos: `python3`, `jq`, e o executável `claude` no `PATH`. A consolidação agendada usa
LaunchAgent no macOS ou cron/systemd no Linux — `/memory-setup` cuida disso.

## O que fica fora do plugin

O **store** e os **logs**. O plugin é descartável; a memória não. Desinstalar não apaga nada do
que foi gravado.

## Custo

O worker roda em Sonnet com o contexto integral da sessão — da ordem de US$ 1 por checkpoint em
sessão longa, algumas vezes por dia de trabalho pesado. A consolidação diária sai de graça
quando não há candidato: o script filtra antes e só chama o modelo se houver o que fazer.

## Limites conhecidos

- A destilação é julgamento de um modelo sem supervisão. As proibições são verificáveis por
  hash; a *qualidade* do resumo só se avalia lendo `~/.claude/memory-consolidate.log`. Vale olhar
  nas primeiras vezes.
- Não há consolidação em níveis: uma memória é generalizada uma vez. Resumo de resumo degrada,
  então, se um dia for feito, deve reler sempre o arquivo original.
- O catálogo de busca escala até uns poucos milhares de memórias. Acima disso, os dossiês passam
  a ser o catálogo.

## Licença

MIT.
