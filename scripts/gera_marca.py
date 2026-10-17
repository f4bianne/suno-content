"""Gera frontend/src/util/marca.ts a partir da logo oficial (frontend/src/assets/suno-logo.png).

A logo tem fundo transparente, parênteses vermelhos e letras quase pretas. Saem duas versões, recortadas e reduzidas:
"clara" (original, para fundo claro) e "escura" (letras claras, para fundo escuro). Vão como data URI porque o SVG
exportado precisa da imagem embutida para abrir fora do site e no Figma.

Uso: python scripts/gera_marca.py
"""
import base64
import io
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = RAIZ / "frontend" / "src" / "assets" / "suno-logo.png"
DESTINO = RAIZ / "frontend" / "src" / "util" / "marca.ts"
LARGURA = 480
LETRA_CLARA = (242, 242, 242)


def png(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    im = Image.open(ORIGEM).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    im = im.resize((LARGURA, round(im.height * LARGURA / im.width)), Image.LANCZOS)
    escura = im.copy()
    px = escura.load()
    for x in range(escura.width):
        for y in range(escura.height):
            r, g, b, a = px[x, y]
            if a and not r > g + 60:          # tudo que não é o vermelho dos parênteses é letra
                px[x, y] = (*LETRA_CLARA, a)
    DESTINO.write_text(
        "// Gerado por scripts/gera_marca.py a partir de frontend/src/assets/suno-logo.png. Não edite à mão.\n"
        f"export const MARCA_PROPORCAO = {im.width / im.height:.4f};   // largura / altura\n"
        f'export const MARCA_CLARA = "{png(im)}";\n'
        f'export const MARCA_ESCURA = "{png(escura)}";\n',
        encoding="utf-8")
    print(f"{DESTINO.relative_to(RAIZ)}: {im.width}x{im.height}, {DESTINO.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
