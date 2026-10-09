"""Detecção de linguagem de recomendação de investimento (proibida em todos os níveis)."""
import re

_PADROES = [
    r"\b(compre|invista|aplique|venda\s+(agora|já|logo|suas?|seus))\b",
    r"\b(recomend(amos|o)|sugerimos|aconselhamos)\b",
    r"\bvale\s+a\s+pena\s+(investir|aplicar|comprar|vender|manter)\b",
    r"\b(é|e)\s+hora\s+de\s+(comprar|vender|investir|aplicar|sair)\b",
    r"\b(deve|devem|deveria|deveriam|precisa|precisam)\s+(comprar|vender|investir|aplicar|migrar|trocar|resgatar)\b",
    r"\bmelhor\s+(momento|hora|opção|investimento)\s+(para|de)\b",
    r"\b(aproveite|não\s+perca|corra)\b",
    r"\b(ganho|retorno|lucro|rendimento)\s+garantid[oa]\b",
    r"\b(oportunidade\s+(única|imperdível|de\s+compra))\b",
]
_REGEX = [re.compile(p, re.IGNORECASE) for p in _PADROES]


def achar(texto: str) -> list[str]:
    """Trechos que casam com algum padrão de recomendação."""
    return [m.group(0) for r in _REGEX for m in r.finditer(texto)]
