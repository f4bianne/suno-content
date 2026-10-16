"""Schemas que o LLM preenche para cada formato (item 17) e conversão para os modelos do avaliador.

Sem valores padrão e com extra="forbid": o modo de saída estruturada estrito exige todos os campos.
"""
from pydantic import BaseModel, ConfigDict

from avaliador.formatos import Artigo, Carrossel, Cena, Conteudo, Roteiro

FORMATOS = ("artigo", "carrossel", "video")


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtigoLLM(_Estrito):
    titulo: str
    corpo: str
    conclusao: str


class CarrosselLLM(_Estrito):
    gancho: str            # slide 1: prende a atenção
    slides_corpo: list[str]
    conclusao: str         # último slide


class CenaLLM(_Estrito):
    fala: str              # narração lida em voz alta
    visual: str            # ação e imagens da cena; na primeira cena é o gancho visual


class RoteiroLLM(_Estrito):
    cenas: list[CenaLLM]


SCHEMA_POR_FORMATO: dict[str, type[BaseModel]] = {"artigo": ArtigoLLM, "carrossel": CarrosselLLM, "video": RoteiroLLM}


def para_conteudo(formato: str, bruto: dict) -> Conteudo:
    """Valida a resposta do LLM e devolve o modelo usado pelo avaliador."""
    modelo = SCHEMA_POR_FORMATO[formato].model_validate(bruto)
    if formato == "artigo":
        return Artigo(titulo=modelo.titulo, corpo=modelo.corpo, conclusao=modelo.conclusao)
    if formato == "carrossel":
        return Carrossel(slides=[modelo.gancho, *modelo.slides_corpo, modelo.conclusao])
    return Roteiro(cenas=marcar_tempo([c.model_dump() for c in modelo.cenas]))


PALAVRAS_POR_SEGUNDO = 2.5


def marcar_tempo(cenas: list[dict], palavras_por_segundo: float = PALAVRAS_POR_SEGUNDO) -> list[Cena]:
    """O tempo de cada cena sai do tamanho da fala, em sequência e sem lacunas: o modelo não precisa (nem consegue
    de forma confiável) contar segundos, e o roteiro fica coerente com o que é dito."""
    cenas_ = []
    acumulado, inicio = 0.0, 0
    for c in cenas:
        acumulado += max(1, len(c["fala"].split())) / palavras_por_segundo
        fim = max(inicio + 1, round(acumulado))
        cenas_.append(Cena(inicio_s=inicio, fim_s=fim, fala=c["fala"], visual=c["visual"]))
        inicio = fim
    return cenas_


def conteudo_em_dict(conteudo: Conteudo) -> dict:
    return conteudo.model_dump()
