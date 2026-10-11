"""Grafo principal: extrai a âncora, dispara os 9 ramos em paralelo e junta os resultados (item 18)."""
import operator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from avaliador import avaliar as av
from avaliador import glossario
from avaliador.ancora import Ancora
from avaliador.juiz import Cliente
from geracao.ramo import ResultadoRamo, construir_ramo, rodar_ramo
from geracao.schemas import FORMATOS
from ingestao import extrator
from ingestao.documento import Documento

NIVEIS = av.NIVEIS


@dataclass
class Clientes:
    extrator: Cliente
    gerador: Cliente
    juiz: Cliente


class EstadoGrafo(TypedDict, total=False):
    documento: Documento
    ancora: Ancora
    descartados: list[tuple[str, str]]
    ramos_pedidos: list[tuple[str, str]]
    resultados: Annotated[list[ResultadoRamo], operator.add]


class Processamento(BaseModel):
    gerado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    documento_chave: str
    origem: str
    url: str | None
    ancora: Ancora
    fatos_descartados: list[tuple[str, str]]
    ramos: list[ResultadoRamo]

    def matriz(self) -> dict[str, dict[str, str]]:
        """nível -> formato -> status ('aprovado' ou 'bloqueado')."""
        m: dict[str, dict[str, str]] = {n: {} for n in NIVEIS}
        for r in self.ramos:
            m[r.nivel][r.formato] = r.status
        return m


def ordenar(pedidos: list[tuple[str, str]], prioritario: str | None) -> list[tuple[str, str]]:
    """Ramos do nível do visitante primeiro: com concorrência limitada, ele sai antes dos outros."""
    if prioritario is None:
        return pedidos
    return sorted(pedidos, key=lambda p: p[0] != prioritario)


def construir_grafo(clientes: Clientes, indice: glossario.Indice, cfg: dict | None = None, max_tentativas: int = 3,
                    max_fatos: int = 12, max_pedacos: int = 6, observador: Callable[[dict], None] | None = None):
    cfg = cfg or av.carregar_config()
    ramo = construir_ramo(clientes.gerador, clientes.juiz, indice, cfg, max_tentativas, observador=observador)

    def avisar(evento: dict) -> None:
        if observador:
            observador(evento)

    def no_extrair(e: EstadoGrafo) -> EstadoGrafo:
        if e.get("ancora") is not None:
            return {}
        avisar({"tipo": "extraindo"})
        ext = extrator.extrair_ancora(clientes.extrator, e["documento"], max_fatos=max_fatos, max_pedacos=max_pedacos)
        avisar({"tipo": "ancora", "fatos": len(ext.ancora.fatos), "descartados": len(ext.descartados)})
        return {"ancora": ext.ancora, "descartados": ext.descartados}

    def espalhar(e: EstadoGrafo):
        if not e["ancora"].fatos:
            raise ValueError("A âncora ficou vazia: o extrator não achou fatos verificáveis no documento.")
        return [Send("ramo", {"par": p, "ancora": e["ancora"]}) for p in e["ramos_pedidos"]]

    def no_ramo(e: dict) -> EstadoGrafo:
        nivel, formato = e["par"]
        limite = cfg["formatos"][formato].get("max_fatos")
        resultado = rodar_ramo(ramo, nivel, formato, e["ancora"], limite)
        avisar({"tipo": "ramo_fim", "nivel": nivel, "formato": formato, "status": resultado.status,
                "tentativas": len(resultado.tentativas)})
        return {"resultados": [resultado]}

    g = StateGraph(EstadoGrafo)
    g.add_node("extrair", no_extrair)
    g.add_node("ramo", no_ramo)
    g.add_edge(START, "extrair")
    g.add_conditional_edges("extrair", espalhar, ["ramo"])
    g.add_edge("ramo", END)
    return g.compile()


def processar(documento: Documento, clientes: Clientes, indice: glossario.Indice, cfg: dict | None = None,
              niveis: tuple[str, ...] = NIVEIS, formatos: tuple[str, ...] = FORMATOS, nivel_prioritario: str | None = None,
              max_tentativas: int = 3, concorrencia: int = 3, ancora: Ancora | None = None,
              observador: Callable[[dict], None] | None = None, **extracao) -> Processamento:
    grafo = construir_grafo(clientes, indice, cfg, max_tentativas, observador=observador, **extracao)
    pedidos = ordenar([(n, f) for n in niveis for f in formatos], nivel_prioritario)
    estado: dict[str, Any] = {"documento": documento, "ramos_pedidos": pedidos}
    if ancora is not None:
        estado["ancora"] = ancora
    final = grafo.invoke(estado, config={"max_concurrency": concorrencia})
    ordem = {p: i for i, p in enumerate(pedidos)}
    ramos = sorted(final["resultados"], key=lambda r: ordem[(r.nivel, r.formato)])
    p = documento.proveniencia
    return Processamento(documento_chave=documento.chave, origem=p.origem, url=p.url, ancora=final["ancora"],
                         fatos_descartados=final.get("descartados", []), ramos=ramos)
