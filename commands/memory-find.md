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

O catálogo é a busca semântica deste sistema: em um store da ordem de centenas de memórias, ler
todas as descrições custa menos e acerta mais que manter um índice vetorial — e entende negação
e nuance, que similaridade de vetor não distingue.

Depois de responder, abra apenas os arquivos que de fato usar. Não despeje o catálogo para o
usuário: ele é insumo seu.
