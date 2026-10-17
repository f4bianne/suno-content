"""Ponto único de entrada: as três portas produzem o mesmo Documento (itens 12 a 15)."""
import httpx

from avaliador import glossario
from ingestao import link, pdf, termo
from ingestao.documento import Documento, Proveniencia


def ingerir_pdf(dados: bytes, nome: str, indice: glossario.Indice | None = None, cfg: dict | None = None) -> Documento:
    return pdf.ler_pdf(dados, nome, indice, cfg)


def ingerir_link(url: str, indice: glossario.Indice | None = None, cfg: dict | None = None,
                 cliente: httpx.Client | None = None) -> Documento:
    return link.ler_link(url, indice, cfg, cliente)


def ingerir_termo(texto: str, indice: glossario.Indice | None = None, cfg: dict | None = None,
                  cliente: httpx.Client | None = None) -> Documento:
    """Resolve o termo para um documento oficial e o ingere; a proveniência registra o termo, o documento achado e a URL."""
    res = termo.resolver(texto, indice, cfg, cliente)
    doc = link.ler_link(res.url, indice, cfg, cliente)
    p = doc.proveniencia
    doc.proveniencia = Proveniencia(tipo="termo", origem=texto, url=p.url or res.url, documento=res.documento or res.fonte,
                                    coletado_em=p.coletado_em, sha256_bruto=p.sha256_bruto)
    return doc
