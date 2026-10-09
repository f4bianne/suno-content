"""Tokenização, divisão em sentenças e contagem de sílabas em português."""
import re
from functools import lru_cache

import pyphen

_PALAVRA = re.compile(r"[0-9A-Za-zÀ-ÿ]+(?:[-'][0-9A-Za-zÀ-ÿ]+)*")
# Fim de sentença: ponto, exclamação, interrogação ou reticências seguidos de espaço e de
# início de nova frase. Números decimais (10,75) e siglas (p.p.) não quebram.
_FIM_SENTENCA = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-Ý0-9\"“(\[])|\n+")
_SILABADOR = pyphen.Pyphen(lang="pt_BR")


def palavras(texto: str) -> list[str]:
    return _PALAVRA.findall(texto)


def sentencas(texto: str) -> list[str]:
    partes = (p.strip() for p in _FIM_SENTENCA.split(texto))
    return [p for p in partes if p and _PALAVRA.search(p)]


@lru_cache(maxsize=50_000)
def silabas(palavra: str) -> int:
    """Número de sílabas. Tokens com algarismo contam como 1 (valem como unidade de leitura)."""
    if any(c.isdigit() for c in palavra):
        return 1
    return _SILABADOR.inserted(palavra.lower()).count("-") + 1
