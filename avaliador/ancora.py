"""Âncora (fatos extraídos do documento), cobertura e conferência de números."""
import re
from dataclasses import dataclass, field

from pydantic import BaseModel

# 10,75% | 1.234,5 | 4.26 | 2025 | R$ 11,5 | 3,2 p.p.
_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


class Fato(BaseModel):
    id: str
    texto: str
    numeros: list[str] = []
    entidades: list[str] = []
    trecho_origem: str = ""


class Ancora(BaseModel):
    fatos: list[Fato]

    def numeros_validos(self) -> set[float]:
        """Todo número que a âncora autoriza: os dos fatos e os dos trechos de origem."""
        valores: set[float] = set()
        for f in self.fatos:
            for fonte in (*f.numeros, f.texto, f.trecho_origem):
                valores.update(numeros_em(fonte))
        return valores


def normalizar_numero(bruto: str) -> float | None:
    """'1.234,5' -> 1234.5; '10,75' -> 10.75; '4.26' -> 4.26; '1.234' -> 1234."""
    s = bruto
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def numeros_em(texto: str) -> list[float]:
    return [v for m in _NUMERO.findall(texto) if (v := normalizar_numero(m)) is not None]


@dataclass
class ResultadoNumeros:
    invalidos: list[str] = field(default_factory=list)
    arredondados: list[str] = field(default_factory=list)


def conferir_numeros(texto: str, ancora: Ancora, permitir_arredondamento: bool, tolerancia: float,
                     marcadores: list[str]) -> ResultadoNumeros:
    """Todo número do texto deve existir na âncora.

    Com `permitir_arredondamento`, aceita-se um valor dentro da tolerância relativa se vier
    precedido de um marcador ("quase", "cerca de") nas três palavras anteriores.
    """
    validos = ancora.numeros_validos()
    res = ResultadoNumeros()
    for m in _NUMERO.finditer(texto):
        v = normalizar_numero(m.group(0))
        if v is None or any(abs(v - x) < 1e-9 for x in validos):
            continue
        if permitir_arredondamento:
            antes = " ".join(texto[:m.start()].split()[-3:]).lower()
            perto = any(abs(v - x) <= tolerancia * abs(x) for x in validos if x)
            if perto and any(mk in antes for mk in marcadores):
                res.arredondados.append(m.group(0))
                continue
        res.invalidos.append(m.group(0))
    return res


@dataclass
class Cobertura:
    fracao: float
    presentes: list[str]
    ausentes: list[str]
    indeterminados: list[str]   # fatos sem número nem entidade: ficam para o Juiz


def cobertura(texto: str, ancora: Ancora) -> Cobertura:
    """Fração dos fatos decidíveis presentes no texto (pelos números ou, sem números, pelas entidades)."""
    no_texto = {round(v, 6) for v in numeros_em(texto)}
    minusculo = texto.lower()
    presentes, ausentes, indeterminados = [], [], []
    for f in ancora.fatos:
        nums = [v for n in f.numeros if (v := normalizar_numero(n)) is not None]
        if not nums and not f.entidades:
            indeterminados.append(f.id)
            continue
        # Com número, o número decide (o texto pode dizer "inflação" em vez de "IPCA").
        # Sem número, as entidades-chave precisam aparecer.
        if nums:
            ok = all(round(v, 6) in no_texto for v in nums)
        else:
            ok = all(e.lower() in minusculo for e in f.entidades)
        (presentes if ok else ausentes).append(f.id)
    decididos = len(presentes) + len(ausentes)
    return Cobertura(len(presentes) / decididos if decididos else 1.0, presentes, ausentes, indeterminados)
