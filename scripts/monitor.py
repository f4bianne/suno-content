"""Verifica as fontes oficiais e gera o conteudo dos documentos que ainda nao estao no banco.

Uso:
  python scripts/monitor.py              (verifica e gera o que for novo)
  python scripts/monitor.py --so-listar  (apenas mostra o que e novo)
"""
import argparse
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from armazenamento import monitor  # noqa: E402
from armazenamento.repositorio import Repositorio  # noqa: E402
from armazenamento.servico import processar_com_banco  # noqa: E402
from avaliador import glossario  # noqa: E402
from avaliador.juiz import ClienteGroq  # noqa: E402
from geracao import grafo  # noqa: E402
from ingestao import entrada  # noqa: E402
from ingestao.clientes import ClienteGemini  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so-listar", action="store_true")
    a = ap.parse_args()

    repo = Repositorio()
    indice = glossario.Indice(glossario.carregar())
    fontes = monitor.verificar(repo, indice)
    for f in fontes:
        estado = "NOVA" if f.nova else ("erro: " + (f.erro or "") if f.erro else "ja no banco")
        print(f"{f.nome:<55} {estado}\n    {f.url or '-'}")
    novas = [f for f in fontes if f.nova]
    print(f"\n{len(novas)} fonte(s) nova(s) de {len(fontes)}.")
    if a.so_listar or not novas:
        return
    groq = ClienteGroq()
    clientes = grafo.Clientes(extrator=groq, gerador=ClienteGemini(), juiz=groq)
    for f in novas:
        print(f"\nGerando: {f.nome}")
        doc = entrada.ingerir_link(f.url, indice)
        p = processar_com_banco(doc, clientes, indice, repo, concorrencia=2)
        print(f"  execucao {p.execucao_id}: {sum(r.status == 'aprovado' for r in p.ramos)}/{len(p.ramos)} aprovados")


if __name__ == "__main__":
    main()
