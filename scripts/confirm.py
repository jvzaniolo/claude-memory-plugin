#!/usr/bin/env python3
"""Marca como consolidadas apenas as memórias que o relatório do modelo confirmou.

Recebe o lote em JSON pela entrada padrão, o relatório na variável RELATORIO e o
caminho do estado no argumento. Sai com 1 quando o relatório não confirma nada,
para que o chamador não avance marcador nenhum.
"""
import datetime
import json
import os
import re
import sys

LINHA_STATUS = re.compile(r'^(consolidada|já-resumida|pulada)[\s|:]*[`\[*]*([^\s`\]*]+\.md)', re.M)
TRATADAS = {'consolidada', 'já-resumida'}
MODIFIED = re.compile(r'^\s*modified:\s*(.+?)\s*$', re.M)


def resolver(citado, esperados):
    """Casa o arquivo citado no relatório com o candidato correspondente.

    O modelo às vezes cita o caminho absoluto dentro do store em vez do relativo.
    """
    if citado in esperados:
        return citado
    for esperado in esperados:
        if citado.endswith('/' + esperado):
            return esperado
    return None


def confirmadas(relatorio, esperados):
    tratadas = set()
    for status, citado in LINHA_STATUS.findall(relatorio):
        arquivo = resolver(citado, esperados)
        if arquivo and status in TRATADAS:
            tratadas.add(arquivo)
    return tratadas


def marcar(estado, store, arquivos, hoje):
    for arquivo in arquivos:
        texto = open(os.path.join(store, arquivo)).read()
        achado = MODIFIED.search(texto)
        estado[arquivo] = {'modified': achado.group(1).strip() if achado else None,
                           'consolidado_em': hoje}
    return estado


def main():
    lote = json.load(sys.stdin)
    esperados = {c['arquivo'] for c in lote['candidatos']}
    tratadas = confirmadas(os.environ.get('RELATORIO', ''), esperados)
    if not tratadas:
        print('relatório não confirmou nenhuma memória', file=sys.stderr)
        return 1

    caminho = sys.argv[1]
    try:
        estado = json.load(open(caminho))
    except Exception:
        estado = {}
    estado = marcar(estado, lote['store'], tratadas, datetime.date.today().isoformat())
    json.dump(estado, open(caminho, 'w'), ensure_ascii=False, indent=2)

    pendentes = esperados - tratadas
    resumo = f'marcadas {len(tratadas)}/{len(esperados)}'
    if pendentes:
        resumo += f'; seguem pendentes: {", ".join(sorted(pendentes))}'
    print(resumo)
    return 0


if __name__ == '__main__':
    sys.exit(main())
