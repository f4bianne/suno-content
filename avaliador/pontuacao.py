"""Nota do avaliador contra o limiar do nível (case, item 5.1.5: "se a pontuação do avaliador for inferior ao limiar
do nível, o grafo faz uma nova iteração").

Antes, qualquer falha reprovava. Com cerca de dez conferências independentes, mesmo 90% de acerto em cada uma dá
0,9^10 ≈ 35% de aprovação, e foi isso que se mediu (37%). Agora há dois tipos de problema:

- bloqueio: o que não pode ir para o ar em ambiente regulado (número fora da âncora, conselho de investimento, vídeo
  acima de 60 s, fidelidade baixa no juiz). Reprova com qualquer nota.
- qualidade: legibilidade, termos, cobertura, formato, rubrica do nível e afirmações duvidosas. Cada uma vira uma nota
  de 0 a 1, e a média ponderada precisa alcançar o limiar do nível.

Pesos, limiar e lista de bloqueios ficam em dados/avaliacao.yaml.
"""
from dataclasses import asdict, dataclass, field

from avaliador.avaliar import Avaliacao
from avaliador.juiz import RUBRICA_POR_NIVEL, Veredito

METRICAS_DO_JUIZ = ("rubrica", "fidelidade")


@dataclass
class Nota:
    total: float
    limiar: float
    por_metrica: dict[str, float]
    bloqueios: list[str] = field(default_factory=list)
    abaixo_do_piso: list[str] = field(default_factory=list)   # a média não esconde uma métrica muito ruim
    juiz: str = "avaliou"          # "avaliou", "nao_chamado" (a nota já não alcançava o limiar) ou "indisponivel"

    @property
    def aprovado(self) -> bool:
        return (not self.bloqueios and not self.abaixo_do_piso and self.juiz == "avaliou"
                and self.total >= self.limiar - 1e-9)

    def em_dict(self) -> dict:
        return {**asdict(self), "aprovado": self.aprovado}

    def resumo(self) -> str:
        """Linha que abre o relatório de falhas: o feedback numérico que o case pede para o reflection loop."""
        partes = ", ".join(f"{m} {v:.2f}" for m, v in self.por_metrica.items() if v < 1)
        txt = f"NOTA {self.total:.2f} (mínimo {self.limiar:.2f})" + (f"; abaixo de 1: {partes}" if partes else "")
        if self.bloqueios:
            txt += f". BLOQUEIOS, que reprovam com qualquer nota: {', '.join(self.bloqueios)}"
        if self.abaixo_do_piso:
            txt += f". Abaixo do mínimo da própria métrica, o que reprova mesmo com média boa: {', '.join(self.abaixo_do_piso)}"
        return txt + "."


def _contar(res: Avaliacao, metrica: str, excluir: str | None = None) -> int:
    return sum(1 for f in res.falhas if f.metrica == metrica and not (excluir and f.mensagem.startswith(excluir)))


def _legibilidade(res: Avaliacao, regras: dict, formato: str, tolerancia: float) -> float:
    flesch = res.metricas.get("flesch")
    if flesch is None:
        return 0.0
    lo, hi = regras.get(f"flesch_{formato}", regras["flesch"])
    v = max(0.0, min(100.0, flesch))
    distancia = max(lo - v, v - hi, 0.0)
    return max(0.0, 1 - distancia / tolerancia)


def _glossario(res: Avaliacao, regras: dict, penalidade: float) -> float:
    nota = max(0.0, 1 - penalidade * _contar(res, "glossario", excluir="densidade"))
    minimo = regras.get("densidade_minima_termos_nivel23_por_100_palavras")
    dens = res.metricas.get("densidade", {}).get("nivel23_por_100_palavras")
    if minimo and dens is not None and dens < minimo:
        nota *= dens / minimo
    return nota


def _cobertura(res: Avaliacao, regras: dict, v: Veredito | None) -> float:
    """Fatos decididos pelas regras mais os indeterminados que o juiz confirmou, contra a cobertura mínima do nível."""
    if "cobertura" not in res.metricas:
        return 1.0
    presentes = len(res.metricas.get("fatos_presentes", []))
    ausentes = len(res.metricas.get("fatos_ausentes", []))
    if v is not None and res.indeterminados:
        presentes += len(set(v.fatos_confirmados) & set(res.indeterminados))
        ausentes += len(set(res.indeterminados) - set(v.fatos_confirmados))
    total = presentes + ausentes
    fracao = presentes / total if total else 1.0
    return min(1.0, fracao / regras["cobertura_minima"])


def pontuar(res: Avaliacao, nivel: str, cfg: dict, veredito: Veredito | None = None, juiz: str = "avaliou") -> Nota:
    """Nota do texto. Sem veredito (juiz não chamado ou fora do ar), as métricas do juiz entram com 1: é o teto possível,
    usado para decidir se vale chamar o juiz."""
    p = cfg["pontuacao"]
    regras = cfg["niveis"][nivel]
    formato = res.metricas.get("formato", "")
    pen = p["penalidade_por_ocorrencia"]

    bloqueios = sorted({f.metrica for f in res.falhas if f.metrica in p["bloqueios"]})
    notas = {
        "legibilidade": _legibilidade(res, regras, formato, p["flesch_tolerancia"]),
        "glossario": _glossario(res, regras, pen),
        "cobertura": _cobertura(res, regras, veredito),
        "formato": max(0.0, 1 - pen * _contar(res, "formato")),
        "rubrica": 1.0,
        "fidelidade": 1.0,
    }
    if veredito is not None:
        n_rubrica = len(RUBRICA_POR_NIVEL[nivel])
        # Vale o pior entre os itens da rubrica e a nota de adequação ao nível (1 a 5): o juiz pode marcar os itens e
        # ainda dizer que o nível está errado, e isso não pode passar com nota cheia.
        notas["rubrica"] = max(0.0, min(1 - len(veredito.criterios_nao_atendidos) / n_rubrica,
                                        (veredito.nota_adequacao_nivel - 1) / 4))
        notas["fidelidade"] = max(0.0, 1 - pen * len(veredito.afirmacoes_sem_suporte))
        if veredito.nota_fidelidade < p["fidelidade_minima_do_juiz"] and "fidelidade" in p["bloqueios"]:
            bloqueios.append("fidelidade")
    pesos = p["pesos"]
    total = sum(pesos[m] * notas[m] for m in pesos) / sum(pesos.values())
    piso = [m for m, minimo in p["piso"].items() if notas[m] < minimo - 1e-9]
    return Nota(round(total, 3), p["limiar"][nivel], {m: round(v, 3) for m, v in notas.items()}, bloqueios, piso, juiz)


def vale_chamar_o_juiz(nota_das_regras: Nota) -> bool:
    """O juiz só pode baixar a nota. Se já há bloqueio, métrica abaixo do piso ou o teto fica abaixo do limiar, a
    chamada não muda o resultado."""
    return (not nota_das_regras.bloqueios and not nota_das_regras.abaixo_do_piso
            and nota_das_regras.total >= nota_das_regras.limiar - 1e-9)
