---
description: Configura a memória de longo prazo — store, retenção de transcript e consolidação diária
---

Você vai configurar a memória de longo prazo deste usuário. São quatro passos; **confirme cada
alteração de configuração antes de aplicá-la** e mostre o que vai mudar.

## 1. Onde o store vai morar

Leia `autoMemoryDirectory` em `~/.claude/settings.json`.

- **Se já existe**, confirme o caminho com o usuário e siga para o passo 2.
- **Se não existe**, explique a escolha e pergunte: por padrão o auto-memory do Claude Code é
  **por repositório** (`~/.claude/projects/<projeto>/memory/`), o que espalha a memória e faz
  com que trabalho num monorepo ou em vários repos não se enxergue. `autoMemoryDirectory` aponta
  todas as sessões para um **pool único**. Sugira `~/.claude/memory` como padrão simples, ou uma
  pasta sincronizada (iCloud/Dropbox) se a pessoa quiser ler de mais de uma máquina — avisando
  que sincronização não é backup versionado.

Crie o diretório se não existir, com um `MEMORY.md` contendo apenas `# Memory Index` e uma linha
em branco. Aplique a chave no `settings.json` com um merge — **nunca reescreva o arquivo inteiro**
— e faça um `.bak` datado antes.

Avise: `autoMemoryDirectory` só é lido no **início** da sessão; a sessão atual continua no pool
antigo até ser reiniciada.

## 2. Retenção do histórico de sessão

Leia `cleanupPeriodDays`. Se não estiver definido, o Claude Code **apaga transcripts com mais de
30 dias, em silêncio**. Explique isso e o que se perde: a memória curada sobrevive, mas o
registro bruto da conversa não.

Pergunte quanto tempo guardar e aplique. Sugira `365`. **Nunca use `0`** — a documentação diz que
0 desliga a limpeza, mas o código trata 0 como "não persistir" e para de escrever transcript.
Avise o custo de disco: da ordem de 1 GB por ano em uso intenso.

## 3. Consolidação diária

Não há nada a configurar — o plugin dispara sozinho, pelo hook `SessionStart`, no máximo uma vez
por dia, em background. Explique o que faz: memórias de tarefa frias há mais de 30 dias e pouco
usadas têm a essência promovida para o dossiê do assunto. **Nada é apagado** — o arquivo
detalhado permanece; muda só o que fica em primeiro plano. Regras de comportamento (`feedback`)
e referências nunca entram.

**Não agende por cron, launchd ou systemd.** Em macOS com o store no iCloud Drive isso não
funciona: iCloud é pasta protegida por TCC, e processo lançado pelo launchd não herda a
permissão da sessão gráfica — recebe "Operation not permitted" até para listar o diretório. A
tarefa roda todo dia, não enxerga nada, e parece saudável no log. O hook roda no contexto do
Claude Code, que já tem acesso ao store.

Se o usuário quiser rodar à mão: `${CLAUDE_PLUGIN_ROOT}/scripts/consolidate.sh`.

## 4. Verificação

Rode `${CLAUDE_PLUGIN_ROOT}/scripts/check.sh` e mostre o resultado. Em store novo ele acusa zero
de tudo, o que é o esperado.

Termine listando o que ficou configurado, onde estão os backups das configs, e como desfazer
cada passo.
