#!/usr/bin/env python3
"""Checagem do parser de confirmação. Rode com: python3 tests/test_confirm.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from confirm import confirmadas  # noqa: E402

LOTE = {
    'shadcn-cli-sobrescreve-vizinhos.md',
    'alert-design-system-sem-variante-warning.md',
    'tasks/ci-testes-unit-lentidao-diagnostico.md',
    'tasks/tanstack-table-v9-frontend.md',
    'tasks/ciatc-turnover-respostas-lilian.md',
}

# Saída real de 22/09, que o validador antigo rejeitava por causa do pipe.
COM_PIPE = """consolidada|alert-design-system-sem-variante-warning.md — acrescentei a diretriz
consolidada|tasks/tanstack-table-v9-frontend.md — acrescentei o achado do React Compiler
já-resumida|shadcn-cli-sobrescreve-vizinhos.md — dossiê já traz regra e ação
já-resumida|tasks/ci-testes-unit-lentidao-diagnostico.md — dossiê já traz causa raiz
já-resumida|tasks/ciatc-turnover-respostas-lilian.md — dossiê já registra o fechamento
"""

# Saída real de 18/09, no formato com espaço, que o validador antigo aceitava.
COM_ESPACO = """consolidada tasks/orfaos-firebase-sem-user-account.md — causa raiz
consolidada tasks/ci-testes-unit-lentidao-diagnostico.md — gargalo era import
já-resumida tasks/tanstack-table-v9-frontend.md — dossiê já cobre
já-resumida shadcn-cli-sobrescreve-vizinhos.md — dossiê já cobre
já-resumida tasks/ciatc-turnover-respostas-lilian.md — dossiê já cobre
"""


def test_aceita_os_dois_separadores():
    assert confirmadas(COM_PIPE, LOTE) == LOTE
    assert confirmadas(COM_ESPACO, LOTE) == LOTE - {'alert-design-system-sem-variante-warning.md'}


def test_pulada_nao_marca():
    relatorio = 'pulada tasks/tanstack-table-v9-frontend.md — dossiê ausente\n'
    assert confirmadas(relatorio, LOTE) == set()


def test_relatorio_parcial_marca_so_o_confirmado():
    relatorio = 'consolidada shadcn-cli-sobrescreve-vizinhos.md — ok\n'
    assert confirmadas(relatorio, LOTE) == {'shadcn-cli-sobrescreve-vizinhos.md'}


def test_ignora_arquivo_fora_do_lote():
    relatorio = 'consolidada memoria-que-nao-estava-no-lote.md — ok\n'
    assert confirmadas(relatorio, LOTE) == set()


def test_aceita_caminho_absoluto_e_crase():
    relatorio = ('consolidada `/Users/x/AgentMemory/tasks/tanstack-table-v9-frontend.md` — ok\n')
    assert confirmadas(relatorio, LOTE) == {'tasks/tanstack-table-v9-frontend.md'}


def test_prosa_sem_relatorio_nao_confirma():
    relatorio = 'Analisei as cinco memórias e atualizei os dossiês. Tudo consistente.\n'
    assert confirmadas(relatorio, LOTE) == set()


if __name__ == '__main__':
    casos = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for caso in casos:
        caso()
        print(f'ok  {caso.__name__}')
    print(f'\n{len(casos)} checagens passaram')
