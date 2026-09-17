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
| **hook `Stop`** | a cada ~120 eventos de transcript, dispara um worker headless que recebe uma cópia do transcript em uma sessão isolada, grava as conclusões duráveis e sai. Não bloqueia sua thread. |
| **hook `PreCompact`** | mesmo worker, disparado antes de a compactação trocar o detalhe da thread por um resumo — sem esperar os ~120 eventos. |
| **`/memory-setup`** | configura pool único, retenção de transcript e a consolidação diária — conversando, com backup e confirmação a cada passo. |
| **`/memory-find`** | busca em duas camadas: `grep` para termo exato, catálogo completo para escolher por sentido. |
| **consolidação diária** | disparada pelo hook `SessionStart`, no máximo 1x/dia, em background: memória de tarefa fria (>30 dias) e pouco usada tem a essência promovida ao dossiê. O arquivo detalhado permanece. |
| **skill `memory-curation`** | o que grava, o que não grava, quando um assunto vira dossiê. |
| **`check.sh`** | integridade: link quebrado, arquivo inalcançável, linha de índice sem arquivo, contador de reincidência divergente. |
| **ordem de leitura** | bloco numerado no topo do `MEMORY.md` dizendo quando ler o quê. Regra certa lida tarde demais não age. |
| **contador de reincidência** | `recurrence:` nas memórias `feedback`, incrementado quando o usuário cobra a mesma regra de novo. É a lista das regras que estão gravadas e mesmo assim não estão pegando. |

## Ideias que sustentam o desenho

**A memória guarda o que não se recupera investigando.** O código está no git, o dado está no
banco, a conversa está no Slack. Antes de gravar: *eu descobriria isso sozinho investigando?* Se
sim, não grave. Esquecer o que é recuperável é saudável — quando precisar, procura-se.

**Dossiês em vez de índice plano.** Um assunto grande ganha um arquivo-índice que nomeia e
resume seus membros; os membros saem do `MEMORY.md`. A cadeia vira `índice → dossiê → arquivo`,
e o teto deixa de morder. Arquivo fora do índice não é órfão quando um dossiê o cobre.

**Concluir não apaga.** O valor de uma memória de tarefa é o domínio que ela carrega — a regra
de negócio, o número medido, o porquê da decisão. Isso sobrevive à entrega. Conteúdo superado permanece com aviso e sucessor explícito.

**Regra de comportamento não envelhece.** Memórias `feedback` e `reference` ficam fora da
consolidação. Abra a fonte antes de aplicar uma regra; o gancho do índice é só um ponteiro. Uso baixo
não é motivo para rebaixar essas memórias.

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

Requisitos: Python 3.9+, `jq` e Claude Code 2.1.248+ no `PATH`, com `--safe-mode` e
`--restricted` disponíveis. O bloqueio usa `fcntl` do Python em macOS/Linux.

**Não agende a consolidação por cron ou launchd.** Com o store no iCloud Drive, um processo do
launchd não herda a permissão TCC da sessão gráfica e recebe "Operation not permitted" até para
listar o diretório — a tarefa roda, não enxerga nada, e o log diz que está tudo bem. Por isso
ela é disparada pelo hook `SessionStart`, que roda no contexto do Claude Code.

## O que fica fora do plugin

O **store** e os **logs**. O plugin é descartável; a memória não. Desinstalar não apaga nada do
que foi gravado.

## Custo

O worker roda em Sonnet e recebe o histórico de mensagens como dados. O custo desta execução
isolada ainda não foi medido; as estimativas do antigo fork não se aplicam automaticamente. A consolidação diária sai de graça
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

## Isolamento e confirmação (0.3.1)

Os workers não retomam a sessão original. Rodam fora do projeto, com `--safe-mode`,
`--restricted`, MCP vazio, hooks desativados e somente Read/Write/Edit/Glob/Grep. Leitura fica
confinada à cópia temporária; escrita é autorizada apenas para Markdown (checkpoint) ou para
os dossiês selecionados (consolidação). O contador de uso é mantido pelo processo local.

O store real só recebe alterações após resultado estruturado válido, verificação de integridade
e comparação com a versão lida antes da chamada. Deleções e alterações fora do escopo abortam
a aplicação. O processo guarda os originais em `~/.claude/memory-backups/` e substitui cada
arquivo atomicamente; o conjunto de arquivos não é uma transação de filesystem.

Checkpoint e consolidação compartilham um bloqueio por caminho canônico do store. O sistema
operacional libera o bloqueio quando o processo morre, sem prazo arbitrário que permita roubar
um bloqueio ainda ativo. Escritas manuais/iCloud não usam esse bloqueio; a comparação detecta
mudanças durante a chamada, mas não elimina uma corrida na janela final de aplicação.

A consolidação confirma cada arquivo separadamente; omitidos e `skipped` continuam pendentes.
O marcador diário só avança após o lote completo ou ausência de candidatos. Falhas são
registradas no log e podem ser retentadas no próximo SessionStart. O checkpoint só avança
após aplicar as alterações validadas. Sessões curtas ainda seguem o piso de 120 eventos
(20 no PreCompact); não há gatilho adicional no encerramento do processo.

`MEM_STATE_DIR` permite testar os estados e logs em diretório temporário. Para verificar:

```sh
python3 -m unittest discover -s tests -v
for script in hooks/*.sh scripts/*.sh; do bash -n "$script" || exit; done
```


## Preferências aplicadas automaticamente (0.3.2)

O checkpoint promove orientações permanentes explícitas na primeira ocorrência e preferências
comportamentais recorrentes para `rules` no frontmatter das memórias `feedback`. Cada regra tem
`key`, `scope`, `instruction` e uma `evidence` literal do corpo da memória. Visitas não promovem
uma memória sozinhas. O worker mantém o histórico da preferência e só atualiza o mesmo assunto
quando o usuário autoriza uma mudança permanente; exceções locais e contradições ambíguas não
substituem a regra vigente.

`scope` é `global` ou o identificador de um repositório, nunca prosa: ele roteia a regra para um
arquivo em disco. A nuance ("no apps/frontend", "ao revisar PR") vai dentro da instrução.
Regra `global` é publicada no `CLAUDE.md` do diretório de estado (`~/.claude` por padrão); regra
de repositório vai para o `CLAUDE.local.md` de cada cópia de trabalho dele, que é pessoal e fica
fora do que o time comita. O mapeamento entre identificador e pastas está em
`memory-scopes.json`, no diretório de estado, e é do usuário:

```json
{ "hu-dashboard": ["~/Developer/hu/dashboard", "~/Developer/hu360/apps/frontend"] }
```

Um identificador pode apontar para várias pastas — a mesma regra alcança as duas cópias do mesmo
repositório. Alcance sem pasta mapeada não publica em lugar nenhum e fica registrado no log.
Pasta onde `CLAUDE.local.md` não esteja ignorado pelo git é recusada: o plugin não cria arquivo
rastreável dentro do repositório de outra pessoa. Use `.git/info/exclude`, que é local.

O processo local valida as fontes e gera a seção entre `<!-- memory:preferences:start -->` e
`<!-- memory:preferences:end -->`, preservando o resto de cada arquivo byte a byte. Links
simbólicos e marcadores incompletos são rejeitados. Mudanças concorrentes abortam a publicação;
os originais entram no mesmo backup das memórias, sob `instructions/`. Regra inválida — evidência
ausente do corpo, chave repetida no mesmo alcance, texto que corromperia os marcadores — é
descartada sozinha e registrada, sem derrubar as demais nem o checkpoint. O que exceder o teto de
10 KB por arquivo também cai com registro. O worker continua sem acesso de escrita a qualquer
arquivo de instrução.

A seção orienta o agente a distinguir exceção local, mudança permanente explícita e conflito
ambíguo; neste último caso, ele deve perguntar o alcance antes de agir. A classificação semântica
continua sendo do modelo: os testes estruturais não garantem obediência em toda conversa.
Novas sessões carregam os arquivos pelo mecanismo nativo. Uma sessão já aberta quando a seção
mudou segue com a versão que carregou no início; a próxima pega a nova.

`python3 scripts/runtime.py bootstrap` percorre as memórias `feedback` existentes e promove as
preferências permanentes já comprovadas, sem esperar uma nova cobrança. É uma passada única, com
chamada ao modelo, que preserva o índice e o corpo das memórias e só acrescenta `rules`. Fora
dela, os pisos de eventos valem normalmente; a sincronização não corrige falhas de captura em
sessões curtas ou excessivamente grandes.

Um índice previamente acima do teto não bloqueia uma alteração que não aumente esse excesso.
