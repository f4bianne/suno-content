"""Acrescenta/atualiza o campo docs_corpus de cada termo de dados/glossario.yaml.

Conta em quantos documentos de dados/corpus/texto/ o termo (ou uma variante) aparece.
Variantes todas em maiúsculas casam só em maiúsculas; as demais, sem diferença de caixa.
Uso: python scripts/docs_corpus.py
"""
import glob
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
CAMINHO = "dados/glossario.yaml"
LETRA = r"[0-9A-Za-zÀ-ÿ]"


_borda = re.compile(LETRA)


def aparece(forma, texto, minusculo):
    """Busca a forma como palavra inteira. Siglas casam em maiúsculas; o resto, sem caixa."""
    base, alvo = (texto, forma) if forma.isupper() else (minusculo, forma.lower())
    i = base.find(alvo)
    while i != -1:
        j = i + len(alvo)
        if not (i > 0 and _borda.match(base[i - 1])) and not (j < len(base) and _borda.match(base[j])):
            return True
        i = base.find(alvo, i + 1)
    return False


def main():
    textos = []
    for f in glob.glob("dados/corpus/texto/*.txt"):
        with open(f, encoding="utf-8") as fh:
            t = fh.read()
        textos.append((t, t.lower()))
    with open(CAMINHO, encoding="utf-8") as f:
        linhas = f.read().split("\n")
    dados = yaml.safe_load("\n".join(linhas))
    contagem = {}
    for t in dados["termos"]:
        formas = [t["termo"], *t.get("variantes", [])]
        contagem[t["termo"]] = sum(any(aparece(x, a, b) for x in formas) for a, b in textos)
    saida = []
    for linha in linhas:
        m = re.match(r'(\s*- \{termo: ")(.+?)(",.*?)(, docs_corpus: \d+)?\}\s*$', linha)
        if m:
            linha = f"{m.group(1)}{m.group(2)}{m.group(3)}, docs_corpus: {contagem[m.group(2)]}}}"
        saida.append(linha)
    with open(CAMINHO, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(saida))
    print(len(textos), "documentos;", len(contagem), "termos")


if __name__ == "__main__":
    main()
