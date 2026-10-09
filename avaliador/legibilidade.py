"""Flesch Reading Ease adaptado ao português (Martins et al., 1996)."""
from dataclasses import dataclass

from avaliador.texto import palavras, sentencas, silabas


@dataclass(frozen=True)
class Legibilidade:
    flesch: float
    palavras: int
    sentencas: int
    silabas: int

    @property
    def palavras_por_sentenca(self) -> float:
        return self.palavras / self.sentencas

    @property
    def silabas_por_palavra(self) -> float:
        return self.silabas / self.palavras


def flesch_pt(texto: str, unidades: list[str] | None = None) -> Legibilidade | None:
    """248,835 − 1,015 × (palavras/sentenças) − 84,6 × (sílabas/palavras).

    `unidades` permite fixar as sentenças (em carrossel, cada slide é uma sentença).
    Devolve None se o texto não tem palavras.
    """
    frases = unidades if unidades is not None else sentencas(texto)
    ps = [p for f in frases for p in palavras(f)]
    if not ps or not frases:
        return None
    sil = sum(silabas(p) for p in ps)
    indice = 248.835 - 1.015 * (len(ps) / len(frases)) - 84.6 * (sil / len(ps))
    return Legibilidade(indice, len(ps), len(frases), sil)
