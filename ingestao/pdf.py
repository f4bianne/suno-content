"""Adaptador de PDF: limites, extração de texto e tabelas e checagem de documento financeiro (item 12)."""
import io

import pdfplumber

from avaliador import glossario
from avaliador.texto import palavras
from ingestao.documento import Documento, ErroIngestao, Proveniencia, carregar_config, normalizar_texto, sha256_bytes


def _tabela_em_texto(linhas: list[list]) -> str:
    return "\n".join(" | ".join((c or "").replace("\n", " ").strip() for c in linha) for linha in linhas)


def parece_financeiro(texto: str, indice: glossario.Indice, cfg: dict) -> tuple[bool, dict]:
    """Aceita se o texto tem termos do glossário em quantidade e variedade suficientes."""
    achados = indice.encontrar(texto)
    distintos = {o.termo.termo for o in achados}
    total = len(palavras(texto)) or 1
    densidade = len(achados) * 100 / total
    ok = len(distintos) >= cfg["termos_distintos_minimos"] and densidade >= cfg["termos_por_100_palavras_minimo"]
    return ok, {"termos_distintos": len(distintos), "termos_por_100_palavras": round(densidade, 2)}


def ler_pdf(dados: bytes, nome: str, indice: glossario.Indice | None = None, cfg: dict | None = None) -> Documento:
    cfg = cfg or carregar_config()
    regras = cfg["pdf"]
    if not dados.startswith(b"%PDF"):
        raise ErroIngestao("O arquivo não é um PDF.")
    if len(dados) > regras["tamanho_maximo_mb"] * 1024 * 1024:
        raise ErroIngestao(f"O PDF passa de {regras['tamanho_maximo_mb']} MB.")
    try:
        pdf = pdfplumber.open(io.BytesIO(dados))
    except Exception as e:
        raise ErroIngestao("Não foi possível abrir o PDF (corrompido ou protegido).") from e
    with pdf:
        if len(pdf.pages) > regras["paginas_maximas"]:
            raise ErroIngestao(f"O PDF tem {len(pdf.pages)} páginas; o máximo é {regras['paginas_maximas']}.")
        paginas, tabelas = [], []
        for n, pagina in enumerate(pdf.pages, 1):
            paginas.append(pagina.extract_text() or "")
            for t in pagina.extract_tables():
                if t:
                    tabelas.append(f"[página {n}]\n{_tabela_em_texto(t)}")
        titulo = (pdf.metadata or {}).get("Title") or None
        total = len(pdf.pages)
    texto = normalizar_texto("\n\n".join(paginas))
    if len(palavras(texto)) < 50:
        raise ErroIngestao("O PDF quase não tem texto (talvez seja imagem escaneada).")
    if indice is not None:
        ok, metricas = parece_financeiro(texto, indice, regras["financeiro"])
        if not ok:
            raise ErroIngestao(
                "O documento não parece financeiro "
                f"({metricas['termos_distintos']} termos do glossário, {metricas['termos_por_100_palavras']} por 100 palavras).")
    return Documento(
        titulo=titulo, texto=texto, paginas=total, tabelas=tabelas,
        proveniencia=Proveniencia(tipo="pdf", origem=nome, sha256_bruto=sha256_bytes(dados)),
    )
