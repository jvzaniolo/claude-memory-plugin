---
description: Busca no store de memória — termo exato via grep, e o catálogo completo para escolher por sentido
argument-hint: [termo]
---

Rode `${CLAUDE_PLUGIN_ROOT}/scripts/find.sh $ARGUMENTS`.

A saída tem duas partes:

1. **LITERAL** — arquivos que contêm o termo exato. Use para identificador: número de PR, nome de
   função, chave de configuração, código de erro.
2. **CATÁLOGO** — uma linha por memória, com tipo e descrição. **Leia a lista inteira** e escolha
   por sentido as memórias que respondem à pergunta; só então abra os arquivos escolhidos.

O catálogo traz apenas o que **não** está no `MEMORY.md`: membros de dossiê e `tasks/`. As
memórias com linha no índice já estão no seu contexto desde o início da sessão, e reimprimi-las
aqui custaria metade da busca sem acrescentar nada. **Escolha entre as duas listas juntas** — o
índice que você já leu e o catálogo. Se precisar mesmo das descrições completas das indexadas,
`find.sh --tudo`.

Juntas, as duas listas são a busca semântica deste sistema: em um store da ordem de centenas de
memórias, ler as descrições custa menos e acerta mais que manter um índice vetorial — e entende
negação e nuance, que similaridade de vetor não distingue.

Depois de responder, abra apenas os arquivos que de fato usar. Não despeje o catálogo para o
usuário: ele é insumo seu.
