"""Extrator: lê o documento e produz a âncora com fatos, números, entidades e trecho de origem (item 16).

A âncora é a referência de verdade do avaliador, então cada fato é conferido contra o documento:
o trecho de origem precisa existir literalmente no texto e conter os números do fato.
"""
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from avaliador.ancora import Ancora, Fato, normalizar_numero, numeros_em
from avaliador.juiz import Cliente, schema_plano
from ingestao.documento import Documento


class FatoBruto(BaseModel):
    """Formato pedido ao LLM. Sem valores padrão, porque o schema estrito exige todos os campos."""
    model_config = ConfigDict(extra="forbid")
    texto: str
    numeros: list[str]
    entidades: list[str]
    trecho_origem: str


class LoteFatos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fatos: list[FatoBruto]


SISTEMA = (
    "Você extrai os FATOS CENTRAIS de um trecho de documento financeiro oficial em português. "
    "Fato central é uma decisão, um número, uma projeção, um risco ou um critério metodológico que um leitor "
    "precisa conhecer. Não opine, não interprete, não use conhecimento externo.\n"
    "Para cada fato devolva:\n"
    "- texto: o fato em uma frase curta e neutra;\n"
    "- numeros: todos os números do fato, escritos exatamente como no documento (ex.: \"14,25\", \"5,06\");\n"
    "- entidades: instituições, índices e conceitos-chave citados (ex.: \"Copom\", \"IPCA\");\n"
    "- trecho_origem: a frase do documento que sustenta o fato, COPIADA LITERALMENTE, sem alterar uma palavra.\n"
    "IGNORE: nomes de pessoas, listas de membros ou de votantes, datas e locais de reunião, endereços, cabeçalhos e rodapés. "
    "Números colados a símbolos como notas de rodapé (por exemplo, o 2 de \"US$²\") não são valores: não os use.\n"
    "Se o trecho não tiver fato central, devolva a lista vazia."
)


_SO_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


def _compacto(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def dividir(texto: str, tamanho: int = 7000) -> list[str]:
    """Pedaços de até `tamanho` caracteres, quebrando em fim de parágrafo ou de linha."""
    pedacos, atual = [], ""
    for linha in texto.split("\n"):
        if atual and len(atual) + len(linha) + 1 > tamanho:
            pedacos.append(atual)
            atual = ""
        atual += (linha + "\n")
    if atual.strip():
        pedacos.append(atual)
    return pedacos


def _densidade_numerica(pedaco: str) -> float:
    return sum(c.isdigit() for c in pedaco) / max(len(pedaco), 1)


def escolher(pedacos: list[str], maximo: int) -> list[str]:
    """Documentos longos: fica com os pedaços mais ricos em números, na ordem original."""
    if len(pedacos) <= maximo:
        return pedacos
    topo = sorted(range(len(pedacos)), key=lambda i: _densidade_numerica(pedacos[i]), reverse=True)[:maximo]
    return [pedacos[i] for i in sorted(topo)]


@dataclass
class Extracao:
    ancora: Ancora
    descartados: list[tuple[str, str]] = field(default_factory=list)   # (motivo, texto do fato)
    chamadas: int = 0


def validar(f: FatoBruto, texto_compacto: str) -> tuple[Fato | None, str]:
    """Aceita o fato só se o trecho existir no documento e contiver seus números."""
    trecho = _compacto(f.trecho_origem)
    if len(trecho) < 20 or trecho not in texto_compacto:
        return None, "trecho de origem não existe no documento"
    no_trecho = {round(v, 6) for v in numeros_em(f.trecho_origem)}
    limpos = []
    for n in f.numeros:
        # O modelo costuma devolver "13,75%" ou "R$ 5,15": fica só o valor numérico.
        achados = _SO_NUMERO.findall(n)
        v = normalizar_numero(achados[0]) if achados else None
        if v is None or round(v, 6) not in no_trecho:
            return None, f"número {n} não aparece no trecho de origem"
        limpos.append(achados[0])
    entidades = [e for e in f.entidades if e.strip() and _compacto(e) in trecho]
    return Fato(id="", texto=f.texto.strip(), numeros=limpos, entidades=entidades,
                trecho_origem=f.trecho_origem.strip()), ""


def extrair_ancora(cliente: Cliente, doc: Documento, max_fatos: int = 24, max_pedacos: int = 12,
                   tamanho_pedaco: int = 7000) -> Extracao:
    compacto = _compacto(doc.texto)
    schema = schema_plano(LoteFatos)
    aceitos: list[Fato] = []
    vistos: set[str] = set()
    res = Extracao(Ancora(fatos=[]))
    for pedaco in escolher(dividir(doc.texto, tamanho_pedaco), max_pedacos):
        res.chamadas += 1
        try:
            lote = LoteFatos.model_validate(cliente.completar_json(SISTEMA, f"TRECHO DO DOCUMENTO:\n{pedaco}", schema))
        except Exception as ex:   # um pedaço que falha não derruba o documento inteiro
            res.descartados.append((f"pedaço do documento falhou ({type(ex).__name__})", pedaco[:60].replace("\n", " ")))
            continue
        for f in lote.fatos:
            fato, motivo = validar(f, compacto)
            if fato is None:
                res.descartados.append((motivo, f.texto))
            elif _compacto(fato.texto) in vistos:
                res.descartados.append(("fato repetido", f.texto))
            else:
                vistos.add(_compacto(fato.texto))
                aceitos.append(fato)
    # Prioriza fatos com número e entidade; a ordem do documento desempata.
    ordem = sorted(range(len(aceitos)), key=lambda i: -((bool(aceitos[i].numeros)) + (bool(aceitos[i].entidades))))
    escolhidos = sorted(ordem[:max_fatos])
    res.ancora = Ancora(fatos=[aceitos[i].model_copy(update={"id": f"f{n}"}) for n, i in enumerate(escolhidos, 1)])
    return res
