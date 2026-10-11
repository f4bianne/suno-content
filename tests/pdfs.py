"""Gera PDFs mínimos para os testes, sem depender de bibliotecas extras."""


def _escapa(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_minimo(paginas: list[list[str]]) -> bytes:
    """Cada página é uma lista de linhas de texto (Helvetica, WinAnsi)."""
    n = len(paginas)
    objetos: list[bytes] = []
    ids_paginas = [4 + 2 * i for i in range(n)]
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{i} 0 R" for i in ids_paginas)
    objetos.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, linhas in enumerate(paginas):
        conteudo = "BT /F1 11 Tf 40 780 Td 14 TL\n" + "\n".join(f"({_escapa(l)}) Tj T*" for l in linhas) + "\nET"
        corpo = conteudo.encode("cp1252")
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {5 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>".encode())
        objetos.append(b"<< /Length " + str(len(corpo)).encode() + b" >>\nstream\n" + corpo + b"\nendstream")
    saida = bytearray(b"%PDF-1.4\n")
    posicoes = []
    for k, obj in enumerate(objetos, 1):
        posicoes.append(len(saida))
        saida += f"{k} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for p in posicoes:
        saida += f"{p:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(saida)


TEXTO_FINANCEIRO = [
    "O Copom elevou a taxa Selic para 14,25% ao ano. A inflacao medida pelo IPCA segue acima da meta.",
    "As expectativas de inflacao permanecem desancoradas e o balanco de riscos exige cautela.",
    "O credito e a inadimplencia das familias e as projecoes de inflacao orientam a politica monetaria.",
    "O mercado de capitais reagiu com alta da volatilidade e o dolar e o cambio oscilaram no periodo.",
    "Os dividendos, os fundos de investimento e a renda fixa tambem foram afetados pelos juros.",
    "O horizonte relevante da politica monetaria depende do hiato do produto e da divida publica.",
]
TEXTO_FINANCEIRO = [l.replace("inflacao", "inflação").replace("balanco", "balanço").replace("credito", "crédito")
                    .replace("projecoes", "projeções").replace("politica", "política").replace("divida", "dívida")
                    .replace("e a inadimplencia", "e a inadimplência").replace("periodo", "período")
                    .replace("tambem", "também") for l in TEXTO_FINANCEIRO]

TEXTO_RECEITA = [
    "Misture a farinha com os ovos e o leite ate formar uma massa lisa e sem grumos para o bolo.",
    "Leve ao forno por quarenta minutos e deixe esfriar antes de servir com cobertura de chocolate.",
    "Os convidados gostaram da sobremesa e pediram a receita para fazer em casa no domingo seguinte.",
    "Use uma forma untada e enfarinhada para o bolo desenformar com facilidade e ficar bonito na mesa.",
]
