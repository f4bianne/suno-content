"""Adaptador de link restrito aos domínios permitidos (item 13)."""
import ipaddress
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from avaliador import glossario
from ingestao import pdf as adaptador_pdf
from ingestao.documento import Documento, ErroIngestao, Proveniencia, carregar_config, normalizar_texto, sha256_bytes

_RUIDO = ["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "iframe"]


def url_permitida(url: str, permitidos: list[dict]) -> bool:
    """Só https, host por nome (nunca IP nem localhost) e dentro de um domínio e caminho permitidos."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not host or host == "localhost" or p.username or p.password:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    for regra in permitidos:
        dom = regra["dominio"]
        if host == dom or host.endswith("." + dom):
            caminhos = regra.get("caminhos")
            if not caminhos or any(p.path == c or p.path.startswith(c + "/") for c in caminhos):
                return True
    return False


def _baixar(url: str, cliente: httpx.Client, regras: dict) -> tuple[bytes, str, str]:
    """Baixa conferindo cada redirecionamento e o tamanho. Devolve (bytes, content-type, url final)."""
    limite = regras["tamanho_maximo_mb"] * 1024 * 1024
    atual = url
    for _ in range(regras["redirecionamentos_maximos"] + 1):
        if not url_permitida(atual, regras["dominios_permitidos"]):
            raise ErroIngestao("Esse endereço não está entre as fontes permitidas.")
        with cliente.stream("GET", atual, follow_redirects=False, timeout=regras["tempo_limite_s"]) as r:
            if r.is_redirect:
                atual = urljoin(atual, r.headers.get("location", ""))
                continue
            if r.status_code >= 400:
                raise ErroIngestao(f"A fonte respondeu com erro {r.status_code}.")
            partes, tamanho = [], 0
            for pedaco in r.iter_bytes():
                tamanho += len(pedaco)
                if tamanho > limite:
                    raise ErroIngestao(f"O arquivo passa de {regras['tamanho_maximo_mb']} MB.")
                partes.append(pedaco)
            return b"".join(partes), r.headers.get("content-type", "").lower(), atual
    raise ErroIngestao("Redirecionamentos demais.")


def texto_de_html(html: bytes) -> tuple[str | None, str]:
    sopa = BeautifulSoup(html, "html.parser")
    titulo = sopa.title.get_text(strip=True) if sopa.title else None
    for tag in sopa(_RUIDO):
        tag.decompose()
    raiz = sopa.find("main") or sopa.find("article") or sopa.body or sopa
    blocos = [b.get_text(" ", strip=True) for b in raiz.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "blockquote"])]
    return titulo, normalizar_texto("\n".join(b for b in blocos if b))


def ler_link(url: str, indice: glossario.Indice | None = None, cfg: dict | None = None,
             cliente: httpx.Client | None = None) -> Documento:
    cfg = cfg or carregar_config()
    regras = cfg["link"]
    url = url.strip()
    if not url_permitida(url, regras["dominios_permitidos"]):
        raise ErroIngestao("Esse endereço não está entre as fontes permitidas (só sites oficiais https).")
    dono = cliente is None
    cliente = cliente or httpx.Client(headers={"User-Agent": "Mozilla/5.0"})
    try:
        dados, tipo, final = _baixar(url, cliente, regras)
    except httpx.HTTPError as e:
        raise ErroIngestao("Não foi possível baixar a fonte.") from e
    finally:
        if dono:
            cliente.close()

    if dados.startswith(b"%PDF") or "pdf" in tipo:
        doc = adaptador_pdf.ler_pdf(dados, final.rsplit("/", 1)[-1] or final, indice, cfg)
        doc.proveniencia = Proveniencia(tipo="link", origem=url, url=final, sha256_bruto=sha256_bytes(dados))
        return doc
    if "html" not in tipo and b"<html" not in dados[:2000].lower():
        raise ErroIngestao("O link não é uma página nem um PDF.")
    titulo, texto = texto_de_html(dados)
    if len(texto.split()) < 50:
        raise ErroIngestao("A página quase não tem texto.")
    if indice is not None:
        ok, m = adaptador_pdf.parece_financeiro(texto, indice, cfg["pdf"]["financeiro"])
        if not ok:
            raise ErroIngestao(f"A página não parece financeira ({m['termos_distintos']} termos do glossário).")
    return Documento(
        titulo=titulo, texto=texto,
        proveniencia=Proveniencia(tipo="link", origem=url, url=final, sha256_bruto=sha256_bytes(dados)),
    )
