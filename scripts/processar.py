"""Roda o pipeline completo (ingestao, ancora, 9 ramos com avaliacao e loop) e guarda o resultado no banco.

Uso:
  python scripts/processar.py --termo Copom
  python scripts/processar.py --link https://www.bcb.gov.br/content/ri/relatorioinflacao/202512/rpm202512b7p.pdf
  python scripts/processar.py --pdf dados/corpus/cvm/resolucao_88.pdf --niveis iniciante --formatos artigo

Os resultados ficam em dados/suno.db (fora do git). Pedir o mesmo documento de novo, com a mesma configuracao,
devolve o resultado guardado sem chamar os modelos; use --forcar para gerar outra versao.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from armazenamento.repositorio import Repositorio  # noqa: E402
from armazenamento.servico import processar_com_banco  # noqa: E402
from avaliador import avaliar as av  # noqa: E402
from avaliador import glossario  # noqa: E402
from avaliador.juiz import ClienteGroq  # noqa: E402
from geracao import grafo  # noqa: E402
from geracao.schemas import FORMATOS  # noqa: E402
from ingestao import entrada  # noqa: E402
from ingestao.clientes import ClienteGemini  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    e = ap.add_mutually_exclusive_group(required=True)
    e.add_argument("--termo")
    e.add_argument("--link")
    e.add_argument("--pdf")
    ap.add_argument("--niveis", nargs="+", choices=av.NIVEIS, default=list(av.NIVEIS))
    ap.add_argument("--formatos", nargs="+", choices=FORMATOS, default=list(FORMATOS))
    ap.add_argument("--prioritario", choices=av.NIVEIS)
    ap.add_argument("--tentativas", type=int, default=3)
    ap.add_argument("--concorrencia", type=int, default=3)
    ap.add_argument("--fatos", type=int, default=12)
    ap.add_argument("--forcar", action="store_true", help="ignora o cache e gera uma nova versao")
    ap.add_argument("--sessao", help="identificador da sessao (PDFs enviados so aparecem para ela)")
    a = ap.parse_args()

    indice = glossario.Indice(glossario.carregar())
    t0 = time.time()
    if a.termo:
        doc = entrada.ingerir_termo(a.termo, indice)
    elif a.link:
        doc = entrada.ingerir_link(a.link, indice)
    else:
        arq = Path(a.pdf)
        doc = entrada.ingerir_pdf(arq.read_bytes(), arq.name, indice)
    print(f"Documento: {doc.proveniencia.url or doc.proveniencia.origem} ({len(doc.texto.split())} palavras)")

    groq = ClienteGroq()
    cl = grafo.Clientes(extrator=groq, gerador=ClienteGemini(), juiz=groq)
    p = processar_com_banco(doc, cl, indice, Repositorio(), niveis=tuple(a.niveis), formatos=tuple(a.formatos),
                            nivel_prioritario=a.prioritario, max_tentativas=a.tentativas, concorrencia=a.concorrencia,
                            max_fatos=a.fatos, sessao=a.sessao, forcar=a.forcar)
    total = time.time() - t0

    print(f"\nAncora: {len(p.ancora.fatos)} fatos ({len(p.fatos_descartados)} descartados)")
    print(f"{'nivel':<15}{'formato':<11}{'status':<11}{'tentativas':<11}{'flesch':<8}falhas da ultima tentativa")
    for r in p.ramos:
        ult = r.tentativas[-1]
        falhas = "; ".join(f.split("]")[0] + "]" for f in ult.falhas) or "-"
        print(f"{r.nivel:<15}{r.formato:<11}{r.status:<11}{len(r.tentativas):<11}{ult.metricas.get('flesch', '-')!s:<8}{falhas}")
    chamadas = sum(t.chamadas_llm for r in p.ramos for t in r.tentativas)
    origem = "do cache (nenhum modelo foi chamado)" if p.do_cache else "gerada agora"
    print(f"\n{chamadas} chamadas de geracao/juiz, {total:.0f}s no total")
    print(f"Execucao {p.execucao_id}, {origem}. Modelos: {p.config.get('modelos')}")


if __name__ == "__main__":
    main()
