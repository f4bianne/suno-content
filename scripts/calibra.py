"""Item 7: mede legibilidade e densidade de termos em textos de referência do corpus.

Cada documento é dividido em parágrafos (30 a 250 palavras) e o Flesch é calculado por parágrafo,
que é a escala dos textos que o sistema vai gerar. Saída: percentis por grupo de documentos.
Uso: python scripts/calibra.py   (requer dados/corpus/texto/, ver scripts/extrai_texto.py)
"""
import glob
import re
import statistics
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from avaliador import glossario  # noqa: E402
from avaliador.legibilidade import flesch_pt  # noqa: E402
from avaliador.texto import palavras  # noqa: E402

GRUPOS = {
    "glossario_bcb (leigo)": "glossarios__bcb_glossario_simplificado",   # parser próprio
    "atas_copom": "atas_copom__",
    "relatorios_bc": "relatorios_bc__",
    "estabilidade_financeira": "estabilidade_financeira__",
    "cvm (normas)": "cvm__",
    "tesouro": "tesouro__",
    "empresas (imprensa)": "empresas__",
}


def _aceita(limpo: str) -> bool:
    ps = palavras(limpo)
    if not 30 <= len(ps) <= 250 or limpo.count(".") < 1 or re.search(r"\.{5,}", limpo):
        return False
    com_digito = sum(any(c.isdigit() for c in p) for p in ps)
    minusculas = sum(p.islower() for p in ps)
    # Descarta endereços, tabelas e índices: muitos números ou poucas palavras comuns.
    return com_digito / len(ps) <= 0.10 and minusculas / len(ps) >= 0.60


def paragrafos(texto: str):
    """Texto de PDF quebra linha no meio da frase: junta linhas até uma linha em branco.
    Em HTML extraído, cada linha já é um bloco."""
    blocos = re.split(r"\n\s*\n", texto)
    if len(blocos) < 5:
        blocos = texto.split("\n")
    vistos = set()
    for bloco in blocos:
        limpo = " ".join(bloco.split())
        if limpo not in vistos and _aceita(limpo):
            vistos.add(limpo)
            yield limpo


def definicoes_glossario(texto: str):
    """Definições do glossário do BC (texto escrito para o público leigo)."""
    corpo = texto[texto.find("Ações\nEm uma empresa"):]
    for m in re.finditer(r"\n[^\n]{2,70}\n(.+?)\n(?:Exemplo|Ver também)", corpo, re.S):
        limpo = " ".join(m.group(1).split())
        if _aceita(limpo):
            yield limpo


def percentis(valores, ps=(10, 25, 50, 75, 90)):
    v = sorted(valores)
    return {p: v[min(len(v) - 1, int(len(v) * p / 100))] for p in ps}


def main():
    indice = glossario.Indice(glossario.carregar())
    print(f"{'grupo':<26}{'parág.':>7}  " + "  ".join(f"P{p:<3}" for p in (10, 25, 50, 75, 90)) + "   nív2-3/100pal")
    for nome, prefixo in GRUPOS.items():
        flesches, dens = [], []
        for arq in glob.glob(f"dados/corpus/texto/{prefixo}*.txt"):
            with open(arq, encoding="utf-8") as f:
                texto = f.read()
                fonte = definicoes_glossario(texto) if nome.startswith("glossario") else paragrafos(texto)
                for p in fonte:
                    r = flesch_pt(p)
                    if r:
                        flesches.append(r.flesch)
                        dens.append(glossario.densidade(p, indice)["nivel23_por_100_palavras"])
        if not flesches:
            print(f"{nome:<26}{0:>7}")
            continue
        pc = percentis(flesches)
        print(f"{nome:<26}{len(flesches):>7}  " + "  ".join(f"{pc[p]:>4.0f}" for p in pc) + f"   {statistics.mean(dens):>6.1f}")


if __name__ == "__main__":
    main()
