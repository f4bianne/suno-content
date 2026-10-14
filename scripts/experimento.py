"""Experimentos (Fase 6): gera varios documentos e produz o relatorio de matriz de confusao, custo e latencia.

Uso:
  python scripts/experimento.py relatorio                 (usa o que ja esta no banco; nao chama modelo)
  python scripts/experimento.py relatorio --llm           (classificador por LLM, alem das regras: gasta tokens)
  python scripts/experimento.py relatorio --salvar resultados.md
  python scripts/experimento.py gerar                     (gera os documentos padrao e guarda no banco)
  python scripts/experimento.py gerar --pdf dados/corpus/cvm/resolucao_88.pdf --pdf outro.pdf

`gerar` guarda cada documento como execucao privada da sessao "experimento" e respeita o cache: documento ja
gerado com a mesma configuracao nao chama modelo de novo (use --forcar para gerar outra versao).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from armazenamento import relatorios  # noqa: E402
from armazenamento.repositorio import Repositorio  # noqa: E402
from armazenamento.servico import processar_com_banco  # noqa: E402
from avaliador import glossario  # noqa: E402
from avaliador.juiz import ClienteGroq, clientes_groq  # noqa: E402
from geracao import grafo  # noqa: E402
from ingestao import entrada  # noqa: E402
from ingestao.clientes import ClienteGemini  # noqa: E402

# Documentos variados do corpus (ver dados/corpus.yaml): duas atas, dois relatorios do BC e uma norma da CVM.
PADRAO = [
    "dados/corpus/atas_copom/ata_269_2025-03-19.pdf",
    "dados/corpus/atas_copom/ata_273_2025-09-17.pdf",
    "dados/corpus/relatorios_bc/rpm_202509.pdf",
    "dados/corpus/estabilidade_financeira/ref_202510.pdf",
    "dados/corpus/cvm/resolucao_88.pdf",
]
SESSAO = "experimento"


def gerar(a):
    indice = glossario.Indice(glossario.carregar())
    repo = Repositorio()
    extrator, juiz = clientes_groq()
    clientes = grafo.Clientes(extrator=extrator, gerador=ClienteGemini(), juiz=juiz)
    caminhos = [Path(p) for p in (a.pdf or PADRAO)]
    faltando = [str(c) for c in caminhos if not c.exists()]
    if faltando:
        sys.exit("Arquivos nao encontrados (rode scripts/baixa_corpus.py): " + ", ".join(faltando))
    for i, arq in enumerate(caminhos, 1):
        print(f"\n[{i}/{len(caminhos)}] {arq.name}", flush=True)
        t0 = time.time()
        try:
            doc = entrada.ingerir_pdf(arq.read_bytes(), arq.name, indice)
            p = processar_com_banco(doc, clientes, indice, repo, max_tentativas=a.tentativas, concorrencia=a.concorrencia,
                                    sessao=SESSAO, forcar=a.forcar)
        except Exception as e:   # um documento ruim nao derruba o lote
            print(f"   ERRO: {type(e).__name__}: {str(e)[:200]}", flush=True)
            continue
        ok = sum(r.status == "aprovado" for r in p.ramos)
        print(f"   {ok}/{len(p.ramos)} aprovados | {'do cache' if p.do_cache else 'gerado'} | {time.time() - t0:.0f} s | execucao {p.execucao_id}", flush=True)


def relatorio(a):
    indice = glossario.Indice(glossario.carregar())
    repo = Repositorio()
    # Cada texto e classificado uma vez so; o modelo menor tem limite de tokens proprio na Groq.
    cliente = relatorios.ClienteComCache(ClienteGroq(modelo=a.modelo)) if a.llm else None
    texto = relatorios.relatorio_markdown(repo, indice, cliente_llm=cliente)
    print(texto)
    if cliente:
        print(f"\n({cliente.chamadas} textos classificados pelo LLM)")
    if a.salvar:
        Path(a.salvar).write_text(texto, encoding="utf-8")
        print(f"\nSalvo em {a.salvar}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gerar")
    g.add_argument("--pdf", action="append", help="caminho de um PDF (pode repetir); sem isso, usa os documentos padrao")
    g.add_argument("--tentativas", type=int, default=3)
    g.add_argument("--concorrencia", type=int, default=3)
    g.add_argument("--forcar", action="store_true")
    r = sub.add_parser("relatorio")
    r.add_argument("--llm", action="store_true")
    r.add_argument("--modelo", default="openai/gpt-oss-20b", help="modelo do classificador por LLM")
    r.add_argument("--salvar")
    a = ap.parse_args()
    {"gerar": gerar, "relatorio": relatorio}[a.cmd](a)


if __name__ == "__main__":
    main()
