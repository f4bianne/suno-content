"""Estruturas mínimas dos três formatos e verificação dos limites (resumo; schemas finais no item 17)."""
import math
from typing import Literal

from pydantic import BaseModel

from avaliador.texto import palavras


class Artigo(BaseModel):
    titulo: str
    corpo: str
    conclusao: str


class Grafico(BaseModel):
    """Gráfico de um slide do corpo do carrossel. Os valores saem dos fatos do documento e são conferidos como números."""
    slide: int                       # índice em `slides` (0 = gancho)
    tipo: Literal["barras", "linha"]
    titulo: str
    rotulos: list[str]               # um por ponto, por exemplo os anos
    valores: list[float]
    unidade: str = ""                # "%", "p.p.", "R$ bi"


class Carrossel(BaseModel):
    slides: list[str]   # primeiro = gancho, último = conclusão
    graficos: list[Grafico] = []


def numero_br(v: float) -> str:
    """4.9 -> '4,9'; 5216.0 -> '5.216'; até 2 casas, sem zeros à direita: o mesmo jeito que os fatos escrevem."""
    inteiro, _, decimais = f"{abs(v):,.2f}".partition(".")
    decimais = decimais.rstrip("0")
    s = inteiro.replace(",", ".") + (f",{decimais}" if decimais else "")
    return f"-{s}" if v < 0 else s


def texto_dos_graficos(conteudo: "Conteudo") -> str:
    """O que os gráficos mostram, em texto: título, rótulos e valores, para conferir números e linguagem."""
    if not isinstance(conteudo, Carrossel):
        return ""
    return "\n".join(f"{g.titulo}: " + "; ".join(f"{r} {numero_br(v)}{g.unidade}" for r, v in zip(g.rotulos, g.valores))
                     for g in conteudo.graficos)


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
        falhas += _verificar_graficos(conteudo, c)
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



def _verificar_graficos(conteudo: Carrossel, c: dict) -> list[str]:
    """Limites dos gráficos: o desenho cabe no slide de 1080 px com folga, mesmo no pior caso permitido aqui."""
    if not conteudo.graficos:
        return []
    g_cfg = c.get("grafico", {})
    falhas: list[str] = []
    maximo = g_cfg.get("maximo", 2)
    if len(conteudo.graficos) > maximo:
        falhas.append(f"carrossel com {len(conteudo.graficos)} gráficos (máximo {maximo})")
    usados: set[int] = set()
    ultimo = len(conteudo.slides) - 1
    lo, hi = g_cfg.get("pontos", [2, 6])
    for g in conteudo.graficos:
        n = g.slide + 1
        if not 0 <= g.slide <= ultimo:
            falhas.append(f"gráfico aponta para o slide {n}, que não existe")
            continue
        if g.slide in (0, ultimo):
            falhas.append(f"gráfico no slide {n}: o gancho e a conclusão não levam gráfico")
        if g.slide in usados:
            falhas.append(f"slide {n} com mais de um gráfico")
        usados.add(g.slide)
        if len(g.rotulos) != len(g.valores):
            falhas.append(f"gráfico do slide {n} com {len(g.rotulos)} rótulos para {len(g.valores)} valores")
        if not lo <= len(g.valores) <= hi:
            falhas.append(f"gráfico do slide {n} com {len(g.valores)} pontos (esperado de {lo} a {hi})")
        if any(not math.isfinite(v) for v in g.valores):
            falhas.append(f"gráfico do slide {n} com valor que não é número")
        if len(g.titulo) > g_cfg.get("caracteres_titulo", 48):
            falhas.append(f"gráfico do slide {n}: título com {len(g.titulo)} caracteres (máximo {g_cfg.get('caracteres_titulo', 48)})")
        for r in g.rotulos:
            if len(r) > g_cfg.get("caracteres_rotulo", 14):
                falhas.append(f"gráfico do slide {n}: rótulo '{r}' com {len(r)} caracteres (máximo {g_cfg.get('caracteres_rotulo', 14)})")
        if len(g.unidade) > g_cfg.get("caracteres_unidade", 6):
            falhas.append(f"gráfico do slide {n}: unidade '{g.unidade}' longa demais (máximo {g_cfg.get('caracteres_unidade', 6)} caracteres)")
        texto = conteudo.slides[g.slide]
        limite = g_cfg.get("caracteres_no_slide", 120)
        if len(texto) > limite:
            falhas.append(f"slide {n} com gráfico tem {len(texto)} caracteres de texto (máximo {limite})")
    return falhas
