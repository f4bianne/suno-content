"""Gera frontend/src/util/medidas.ts: largura de cada caractere na Arial (normal e negrito), em milésimos de em.

O SVG dos slides é desenhado sem navegador (também nos testes), então a largura do texto vem desta tabela, medida na
fonte de verdade. Caracteres fora da tabela usam a largura do mais largo, o que só deixa sobra.

Uso: python scripts/gera_medidas.py
"""
import json
from pathlib import Path

from PIL import ImageFont

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "frontend" / "src" / "util" / "medidas.ts"
FONTES = {"normal": r"C:\Windows\Fonts\arial.ttf", "negrito": r"C:\Windows\Fonts\arialbd.ttf"}
CARACTERES = "".join(chr(c) for c in range(32, 127)) + "".join(chr(c) for c in range(160, 256)) + "–—‘’“”•…€"


def main() -> None:
    linhas = ["// Gerado por scripts/gera_medidas.py (Arial medida com Pillow). Não edite à mão.",
              f"export const CARACTERES = {json.dumps(CARACTERES)};"]
    for nome, caminho in FONTES.items():
        f = ImageFont.truetype(caminho, 1000)
        larguras = [round(f.getlength(c)) for c in CARACTERES]
        linhas.append(f"export const LARGURA_{nome.upper()} = [{', '.join(map(str, larguras))}];")
        linhas.append(f"export const MAIS_LARGO_{nome.upper()} = {max(larguras)};")
    DESTINO.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"{DESTINO.relative_to(RAIZ)}: {len(CARACTERES)} caracteres")


if __name__ == "__main__":
    main()
