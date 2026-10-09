"""Classificador cego do nível e matriz de confusão (roadmap, item 11).

O classificador recebe só o texto, nunca o nível-alvo. Se ele acerta o nível que o gerador
tentou produzir, os níveis são distinguíveis. Há dois: um por regras (determinístico, serve de
referência) e um por LLM (a ser comparado).
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from avaliador import glossario
from avaliador.juiz import Cliente
from avaliador.legibilidade import flesch_pt

NIVEIS = ("iniciante", "intermediario", "avancado")


class Palpite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nivel: Literal["iniciante", "intermediario", "avancado"]
    justificativa: str


def classificar_por_regras(texto: str, indice: glossario.Indice) -> str:
    """Nível mais baixo que o texto respeita: não tem termo acima do permitido sem explicação."""
    for nivel, (sem, com) in (("iniciante", (1, 2)), ("intermediario", (2, 3))):
        if not glossario.violacoes(texto, indice, sem, com):
            leg = flesch_pt(texto)
            # Um texto sem termos difíceis mas de leitura pesada não é iniciante.
            if nivel == "iniciante" and leg and leg.flesch < 50:
                continue
            return nivel
    return "avancado"


SISTEMA_CLASSIFICADOR = (
    "Classifique o texto financeiro abaixo pelo público a que se destina:\n"
    "- iniciante: sem jargão financeiro sem analogia do dia a dia; foco no impacto no bolso;\n"
    "- intermediario: vocabulário de mercado padrão (CDI, Selic, IPCA, dividendos); foco em alocação e tendências;\n"
    "- avancado: jargão pleno (curva de juros, forward guidance, hiato do produto, EBITDA ajustado, covenants); foco analítico.\n"
    "Responda apenas com o nível."
)


def classificar_por_llm(cliente: Cliente, texto: str) -> str:
    bruto = cliente.completar_json(SISTEMA_CLASSIFICADOR, texto, Palpite.model_json_schema())
    return Palpite.model_validate(bruto).nivel


def matriz_confusao(reais: list[str], previstos: list[str]) -> dict[str, dict[str, int]]:
    """Linhas = nível real; colunas = nível previsto."""
    if len(reais) != len(previstos):
        raise ValueError("listas de tamanhos diferentes")
    m = {r: {p: 0 for p in NIVEIS} for r in NIVEIS}
    for r, p in zip(reais, previstos):
        m[r][p] += 1
    return m


def acuracia(matriz: dict[str, dict[str, int]]) -> float:
    total = sum(sum(l.values()) for l in matriz.values())
    return sum(matriz[n][n] for n in NIVEIS) / total if total else 0.0


def formatar(matriz: dict[str, dict[str, int]]) -> str:
    linhas = ["real \\ previsto  " + "  ".join(f"{n[:5]:>5}" for n in NIVEIS)]
    for r in NIVEIS:
        linhas.append(f"{r:<16}  " + "  ".join(f"{matriz[r][p]:>5}" for p in NIVEIS))
    return "\n".join(linhas)
