"""Estruturas mínimas dos três formatos e verificação dos limites (resumo; schemas finais no item 17)."""
from pydantic import BaseModel

from avaliador.texto import palavras


class Artigo(BaseModel):
    titulo: str
    corpo: str
    conclusao: str


class Carrossel(BaseModel):
    slides: list[str]   # primeiro = gancho, último = conclusão


class Cena(BaseModel):
    inicio_s: float
    fim_s: float
    fala: str
    visual: str


class Roteiro(BaseModel):
    cenas: list[Cena]


Conteudo = Artigo | Carrossel | Roteiro


def formato_de(conteudo: Conteudo) -> str:
    return {Artigo: "artigo", Carrossel: "carrossel", Roteiro: "video"}[type(conteudo)]


def texto_corrido(conteudo: Conteudo) -> str:
    """Texto que o leitor lê ou ouve, usado em todas as métricas (o que se exibe é o que se avalia)."""
    if isinstance(conteudo, Artigo):
        return f"{conteudo.titulo}\n{conteudo.corpo}\n{conteudo.conclusao}"
    if isinstance(conteudo, Carrossel):
        return "\n".join(conteudo.slides)
    return "\n".join(c.fala for c in conteudo.cenas)


def unidades_flesch(conteudo: Conteudo) -> list[str] | None:
    """Em carrossel, cada slide do corpo é uma sentença; gancho e conclusão ficam de fora porque são curtos por
    natureza e inflariam o índice. Nos demais formatos, a divisão em sentenças é automática."""
    if not isinstance(conteudo, Carrossel):
        return None
    return list(conteudo.slides[1:-1]) if len(conteudo.slides) >= 3 else list(conteudo.slides)


def verificar(conteudo: Conteudo, cfg: dict) -> list[str]:
    """Falhas de limite de formato (lista vazia = ok)."""
    falhas: list[str] = []
    if isinstance(conteudo, Artigo):
        n = len(palavras(texto_corrido(conteudo)))
        lo, hi = cfg["artigo"]["palavras"]
        if not lo <= n <= hi:
            falhas.append(f"artigo com {n} palavras (esperado de {lo} a {hi})")
        if not conteudo.titulo.strip():
            falhas.append("artigo sem título")
        if not conteudo.conclusao.strip():
            falhas.append("artigo sem conclusão")
    elif isinstance(conteudo, Carrossel):
        c = cfg["carrossel"]
        lo, hi = c["slides"]
        if not lo <= len(conteudo.slides) <= hi:
            falhas.append(f"carrossel com {len(conteudo.slides)} slides (esperado de {lo} a {hi})")
        for i, s in enumerate(conteudo.slides, 1):
            if len(s) > c["caracteres_por_slide"]:
                falhas.append(f"slide {i} com {len(s)} caracteres (máximo {c['caracteres_por_slide']})")
            if not s.strip():
                falhas.append(f"slide {i} vazio")
    else:
        v = cfg["video"]
        if not conteudo.cenas:
            return ["roteiro sem cenas"]
        fim = max(c.fim_s for c in conteudo.cenas)
        if fim > v["duracao_maxima_s"]:
            falhas.append(f"roteiro marca {fim:g}s (máximo {v['duracao_maxima_s']}s)")
        falado = len(palavras(texto_corrido(conteudo)))
        estimado = falado / v["palavras_por_segundo"]
        if estimado > v["duracao_maxima_s"]:
            falhas.append(f"fala de {falado} palavras leva cerca de {estimado:.0f}s (máximo {v['duracao_maxima_s']}s)")
        if not conteudo.cenas[0].visual.strip():
            falhas.append("roteiro sem gancho visual na primeira cena")
        for i, c in enumerate(conteudo.cenas, 1):
            if c.fim_s <= c.inicio_s:
                falhas.append(f"cena {i} com marcação de tempo inválida")
    return falhas

