"""Leitura do glossário, busca de termos no texto e verificação das regras por nível."""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from avaliador.texto import palavras, sentencas

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "glossario.yaml"
_LETRA = r"[0-9A-Za-zÀ-ÿ]"

# Marcadores que, na mesma frase ou na anterior, indicam que o termo foi explicado.
_MARCADORES_FRASE = re.compile(
    r"\b(ou seja|isto é|isso é|quer dizer|em outras palavras|como se fosse|funciona como|"
    r"é como|é a mesma coisa que|imagine|pense em|significa|chamad[oa]|conhecid[oa] como)\b",
    re.IGNORECASE,
)
# Logo antes do termo: "a taxa chamada Selic", "conhecido como Copom".
_LOGO_ANTES = re.compile(r"(chamad[oa]s?|conhecid[oa]s? como|denominad[oa]s?|sigla|sigla de)\s*$", re.IGNORECASE)
# Logo depois do termo: "(definição)", "— definição", ", que é ...", ", ou seja ...".
_LOGO_APOS = re.compile(r"^\s*(\(|—|–| - |,\s*(que|ou seja|isto é|a|o)\b|\s+é\s+(a|o|um|uma)\b)", re.IGNORECASE)


@dataclass(frozen=True)
class Termo:
    termo: str
    nivel: int
    categoria: str
    formas: tuple[str, ...]
    ambiguo: bool = False


@dataclass(frozen=True)
class Ocorrencia:
    termo: Termo
    forma: str
    inicio: int
    fim: int


@dataclass(frozen=True)
class Violacao:
    termo: str
    nivel_termo: int
    motivo: str   # "proibido" ou "sem explicacao"
    trecho: str


def carregar(caminho: Path = CAMINHO_PADRAO) -> list[Termo]:
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    return [
        Termo(
            termo=t["termo"],
            nivel=t["nivel"],
            categoria=t["categoria"],
            formas=tuple([t["termo"], *t.get("variantes", [])]),
            ambiguo=bool(t.get("ambiguo", False)),
        )
        for t in dados["termos"]
    ]


def _padrao(forma: str) -> re.Pattern:
    # Siglas (tudo em maiúsculas) casam só em maiúsculas; o resto ignora caixa e aceita plural.
    corpo = re.escape(forma)
    if forma.isupper():
        return re.compile(rf"(?<!{_LETRA}){corpo}(?!{_LETRA})")
    return re.compile(rf"(?<!{_LETRA}){corpo}(?:s|es)?(?!{_LETRA})", re.IGNORECASE)


class Indice:
    """Formas do glossário pré-compiladas, da mais longa para a mais curta."""

    def __init__(self, termos: list[Termo]):
        self.termos = termos
        itens = [(f, t) for t in termos for f in t.formas]
        itens.sort(key=lambda x: len(x[0]), reverse=True)
        self._itens = [(f, t, _padrao(f)) for f, t in itens]

    def encontrar(self, texto: str, incluir_ambiguos: bool = False) -> list[Ocorrencia]:
        """Ocorrências sem sobreposição; vale a forma mais longa."""
        ocupado: list[tuple[int, int]] = []
        achados: list[Ocorrencia] = []
        for forma, termo, padrao in self._itens:
            if termo.ambiguo and not incluir_ambiguos:
                continue
            for m in padrao.finditer(texto):
                if any(m.start() < f and i < m.end() for i, f in ocupado):
                    continue
                ocupado.append((m.start(), m.end()))
                achados.append(Ocorrencia(termo, forma, m.start(), m.end()))
        return sorted(achados, key=lambda o: o.inicio)


def _limites_sentencas(texto: str) -> list[tuple[int, int]]:
    limites, pos = [], 0
    for s in sentencas(texto):
        i = texto.find(s, pos)
        if i == -1:
            continue
        limites.append((i, i + len(s)))
        pos = i + len(s)
    return limites


def explicado(o: Ocorrencia, texto: str, limites: list[tuple[int, int]] | None = None) -> bool:
    """O termo vem com explicação: marcador logo depois, ou marcador na mesma frase ou na anterior."""
    if _LOGO_APOS.match(texto[o.fim:o.fim + 40]) or _LOGO_ANTES.search(texto[max(0, o.inicio - 25):o.inicio]):
        return True
    limites = limites if limites is not None else _limites_sentencas(texto)
    for k, (i, f) in enumerate(limites):
        if i <= o.inicio < f:
            ini = limites[k - 1][0] if k > 0 else i
            return bool(_MARCADORES_FRASE.search(texto[ini:f]))
    return False


def violacoes(texto: str, indice: Indice, maximo_sem_explicacao: int, maximo_com_explicacao: int) -> list[Violacao]:
    """Termos acima do permitido para o nível.

    - nível do termo > maximo_com_explicacao: proibido, mesmo explicado;
    - nível do termo > maximo_sem_explicacao: aceito só com explicação.

    Uma explicação vale para o termo daí em diante (inclusive para sinônimos dele). Uma menção
    sem explicação é perdoada se a explicação vem logo depois (até 250 caracteres), como em
    "O Copom decidiu... O Copom é o comitê que...". Menções antes disso são violações.
    """
    limites = _limites_sentencas(texto)
    achadas = []
    ja_explicados: set[str] = set()
    ocorrencias = indice.encontrar(texto)
    explicadas_em = {}   # termo -> posições das ocorrências explicadas
    for oc in ocorrencias:
        if explicado(oc, texto, limites):
            explicadas_em.setdefault(oc.termo.termo, []).append(oc.inicio)
    for o in ocorrencias:
        n = o.termo.nivel
        if n <= maximo_sem_explicacao:
            continue
        trecho = texto[max(0, o.inicio - 30):o.fim + 30].replace("\n", " ")
        if n > maximo_com_explicacao:
            achadas.append(Violacao(o.termo.termo, n, "proibido", trecho))
        elif explicado(o, texto, limites):
            ja_explicados.add(o.termo.termo)
        elif o.termo.termo not in ja_explicados and not any(
                0 < p - o.fim <= 250 for p in explicadas_em.get(o.termo.termo, [])):
            achadas.append(Violacao(o.termo.termo, n, "sem explicacao", trecho))
    return achadas


def densidade(texto: str, indice: Indice) -> dict:
    """Termos por nível e por 100 palavras."""
    total = len(palavras(texto)) or 1
    por_nivel = {1: 0, 2: 0, 3: 0}
    for o in indice.encontrar(texto):
        por_nivel[o.termo.nivel] += 1
    return {
        "contagem": por_nivel,
        "por_100_palavras": {n: round(c * 100 / total, 2) for n, c in por_nivel.items()},
        "nivel23_por_100_palavras": round((por_nivel[2] + por_nivel[3]) * 100 / total, 2),
    }
