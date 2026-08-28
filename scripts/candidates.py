#!/usr/bin/env python3
"""Seleciona memórias candidatas à consolidação episódico→semântico.

Candidata = type:project + coberta por um dossiê + fria (modified > N dias)
            + pouco usada + ainda não consolidada.

Regras de segurança:
  - feedback e reference NUNCA entram (regra de comportamento não envelhece)
  - memória sem dossiê que a cubra NUNCA entra (não haveria para onde promover)
  - uso alto PROTEGE; uso zero não condena (o índice age sem abrir arquivo)
Imprime JSON no stdout. Não escreve nada.
"""
import os, re, glob, json, sys, datetime

STORE = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1
    else os.environ.get("MEM_STORE", ""))
if not STORE or not os.path.isdir(STORE):
    sys.exit("erro: informe o store como argumento ou em MEM_STORE")
DIAS = int(os.environ.get("MEM_COLD_DAYS", "30"))
USO_PROTEGE = int(os.environ.get("MEM_USE_SHIELD", "3"))
JANELA_USO = int(os.environ.get("MEM_USE_WINDOW", "90"))   # dias em que um uso ainda escuda
USAGE = os.path.join(STORE, ".memory-usage.json")
STATE = os.path.expanduser("~/.claude/memory-consolidated.json")  # estado fora do store

def carrega(p, critico=False):
    """critico=True: arquivo corrompido ABORTA. Seguir sem o contador de uso
    removeria o escudo das memórias mais usadas — falha na direção errada."""
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception as e:
        if critico:
            sys.exit(f"erro: {p} ilegível ({e}). Abortando: sem o contador de uso, "
                     f"memórias protegidas entrariam na fila de consolidação.")
        return {}

uso, consolidado = carrega(USAGE, critico=True), carrega(STATE)
hoje = datetime.date.today()

def campo(txt, nome):
    m = re.search(rf'^\s*{nome}:\s*(.+?)\s*$', txt, re.M)
    return m.group(1).strip().strip('"') if m else None

arquivos = {os.path.relpath(p, STORE): p
            for p in glob.glob(os.path.join(STORE, "**", "*.md"), recursive=True)
            if os.path.basename(p) != "MEMORY.md"}

# dossiês: arquivo cujo frontmatter se declara dossiê/índice temático
dossies, membro_de = {}, {}
for rel, p in arquivos.items():
    txt_d = open(p).read()
    cab = txt_d[:700]
    # explícito vence heurística: `role: dossier` no frontmatter é o contrato.
    # A heurística por palavra existe só para store anterior a essa convenção.
    eh_dossie = bool(re.search(r'^\s*role:\s*dossier\s*$', cab, re.M)) \
                or "dossiê" in cab.lower() or "Índice temático" in cab
    if eh_dossie:
        dossies[rel] = True
        for slug in re.findall(r"\[\[([^\]]+)\]\]", open(p).read()):
            membro_de.setdefault(slug + ".md", rel)

cands = []
for rel, p in arquivos.items():
    if rel in dossies: continue
    txt = open(p).read()
    if (campo(txt, "type") or "") != "project": continue
    dossie = membro_de.get(rel)
    if not dossie: continue
    mod = campo(txt, "modified")
    if mod:
        try: dias = (hoje - datetime.date.fromisoformat(mod[:10])).days
        except ValueError: dias = None
    else: dias = None
    if dias is None:  # sem campo confiável: cai no mtime, mas exige o dobro de frieza
        dias = int((datetime.datetime.now().timestamp() - os.path.getmtime(p)) / 86400)
        if dias < DIAS * 2: continue
    elif dias < DIAS: continue
    reg = uso.get(rel, {})
    total = reg.get("uses", 0)
    # escudo decai: só conta uso dentro da janela. O total histórico nunca decresce,
    # mas deixa de proteger quando o assunto esfria de vez.
    recentes = 0
    for d in reg.get("recent", []):
        try:
            if (hoje - datetime.date.fromisoformat(d[:10])).days <= JANELA_USO: recentes += 1
        except ValueError: pass
    if not reg.get("recent") and total:      # registro antigo, sem histórico de datas
        ultimo = reg.get("last_used")
        try:
            if ultimo and (hoje - datetime.date.fromisoformat(ultimo[:10])).days <= JANELA_USO:
                recentes = total
        except ValueError: pass
    if recentes >= USO_PROTEGE: continue              # usada de verdade e há pouco: protegida
    u = recentes
    if consolidado.get(rel, {}).get("modified") == mod: continue   # já consolidada nessa versão
    cands.append({"arquivo": rel, "dossie": dossie, "dias": dias,
                  "usos_recentes": u, "usos_total": total,
                  "linhas": len(txt.splitlines()),
                  "description": campo(txt, "description")})

# fila: mais frio primeiro; entre iguais, o que nunca importou historicamente vem antes
cands.sort(key=lambda c: (-c["dias"], c["usos_total"]))
print(json.dumps({"store": STORE, "limite_dias": DIAS,
                  "total": len(cands), "candidatos": cands}, ensure_ascii=False, indent=2))
