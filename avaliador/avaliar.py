"""Avaliação determinística: junta legibilidade, glossário, formato, números, cobertura e recomendação."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from avaliador import ancora as anc
from avaliador import formatos, glossario, recomendacao
from avaliador.legibilidade import flesch_pt

CONFIG_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "avaliacao.yaml"
NIVEIS = ("iniciante", "intermediario", "avancado")


def carregar_config(caminho: Path = CONFIG_PADRAO) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Falha:
    metrica: str
    mensagem: str


@dataclass
class Avaliacao:
    aprovado: bool
    falhas: list[Falha] = field(default_factory=list)
    metricas: dict = field(default_factory=dict)
    indeterminados: list[str] = field(default_factory=list)   # fatos que o Juiz precisa confirmar

    def resumo(self) -> str:
        if self.aprovado:
            return "aprovado"
        return "reprovado: " + "; ".join(f"[{f.metrica}] {f.mensagem}" for f in self.falhas)


def avaliar(conteudo: formatos.Conteudo, nivel: str, indice: glossario.Indice,
            ancora: anc.Ancora | None = None, cfg: dict | None = None) -> Avaliacao:
    """Aplica todas as métricas determinísticas ao conteúdo de um ramo (nível x formato)."""
    if nivel not in NIVEIS:
        raise ValueError(f"nível desconhecido: {nivel}")
    cfg = cfg or carregar_config()
    regras = cfg["niveis"][nivel]
    texto = formatos.texto_corrido(conteudo)
    falhas: list[Falha] = []
    metricas: dict = {"nivel": nivel, "formato": formatos.formato_de(conteudo)}

    # Formato
    for msg in formatos.verificar(conteudo, cfg["formatos"]):
        falhas.append(Falha("formato", msg))

    # Legibilidade
    leg = flesch_pt(texto, formatos.unidades_flesch(conteudo))
    if leg is None:
        falhas.append(Falha("legibilidade", "texto vazio"))
    else:
        metricas["flesch"] = round(leg.flesch, 1)
        # A fala de vídeo tem frases curtas por natureza e ganha uma faixa própria.
        lo, hi = regras.get(f"flesch_{metricas['formato']}", regras["flesch"])
        # A escala é de 0 a 100; textos muito simples passam de 100, o que não é defeito.
        if not lo <= max(0.0, min(100.0, leg.flesch)) <= hi:
            falhas.append(Falha("legibilidade", f"Flesch {leg.flesch:.1f} fora da faixa {lo} a {hi}"))

    # Termos do glossário
    for v in glossario.violacoes(texto, indice, regras["nivel_maximo_termo_sem_explicacao"],
                                 regras["nivel_maximo_termo_com_explicacao"]):
        falhas.append(Falha("glossario", f"termo de nível {v.nivel_termo} {v.motivo}: '{v.termo}' em \"...{v.trecho}...\""))
    dens = glossario.densidade(texto, indice)
    metricas["densidade"] = dens
    minimo = regras.get("densidade_minima_termos_nivel23_por_100_palavras")
    if minimo is not None and dens["nivel23_por_100_palavras"] < minimo:
        falhas.append(Falha("glossario", f"densidade de termos nível 2-3 {dens['nivel23_por_100_palavras']} abaixo de {minimo} por 100 palavras"))

    # Recomendação
    for trecho in recomendacao.achar(texto):
        falhas.append(Falha("recomendacao", f"linguagem de recomendação: \"{trecho}\""))

    # Âncora: números e cobertura
    indeterminados: list[str] = []
    if ancora is not None:
        n = cfg["numeros"]
        res = anc.conferir_numeros(texto, ancora, nivel in n["arredondamento_permitido_em"],
                                   n["tolerancia_relativa"], n["marcadores"])
        for x in res.invalidos:
            falhas.append(Falha("numeros", f"número '{x}' não existe na âncora"))
        metricas["numeros_arredondados"] = res.arredondados
        cob = anc.cobertura(texto, ancora)
        metricas["cobertura"] = round(cob.fracao, 3)
        metricas["fatos_ausentes"] = cob.ausentes
        indeterminados = cob.indeterminados
        if cob.fracao < regras["cobertura_minima"]:
            falhas.append(Falha("cobertura", f"cobertura {cob.fracao:.0%} abaixo de {regras['cobertura_minima']:.0%}; ausentes: {', '.join(cob.ausentes)}"))

    return Avaliacao(not falhas, falhas, metricas, indeterminados)
