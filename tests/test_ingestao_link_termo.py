from datetime import date

import httpx
import pytest

from avaliador import glossario
from ingestao import documento, link, termo
from ingestao.documento import ErroIngestao
from ingestao.entrada import ingerir_link, ingerir_termo
from tests.pdfs import TEXTO_FINANCEIRO, pdf_minimo

CFG = documento.carregar_config()
PERMITIDOS = CFG["link"]["dominios_permitidos"]
HTML = ("<html><head><title>Copom eleva a Selic</title></head><body><nav>menu</nav><main>"
        + "".join(f"<p>{l}</p>" for l in TEXTO_FINANCEIRO * 2) + "</main><footer>rodapé</footer></body></html>").encode()


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


def cliente(respostas: dict, chamadas: list | None = None):
    """Cliente HTTP falso. `respostas` mapeia URL -> (status, content-type, corpo[, location])."""
    def tratar(req: httpx.Request) -> httpx.Response:
        if chamadas is not None:
            chamadas.append((req.method, str(req.url)))
        status, tipo, corpo, *loc = respostas.get(str(req.url), (404, "text/plain", b""))
        cab = {"content-type": tipo}
        if loc:
            cab["location"] = loc[0]
        return httpx.Response(status, headers=cab, content=corpo)
    return httpx.Client(transport=httpx.MockTransport(tratar))


@pytest.mark.parametrize("url,esperado", [
    ("https://www.bcb.gov.br/content/copom/ata.pdf", True),
    ("https://conteudo.cvm.gov.br/x.pdf", True),
    ("https://www.gov.br/cvm/pt-br/assuntos", True),
    ("https://www.gov.br/receitafederal/pt-br", False),       # gov.br fora dos caminhos permitidos
    ("http://www.bcb.gov.br/ata.pdf", False),                  # sem https
    ("https://bcb.gov.br.malicioso.com/x", False),             # domínio parecido
    ("https://malicioso.com/bcb.gov.br", False),
    ("https://127.0.0.1/x", False),
    ("https://localhost/x", False),
    ("https://user:senha@www.bcb.gov.br/x", False),
    ("ftp://www.bcb.gov.br/x", False),
    ("nao e url", False),
])
def test_url_permitida(url, esperado):
    assert link.url_permitida(url, PERMITIDOS) is esperado


def test_pagina_html_vira_documento_sem_ruido(indice):
    url = "https://agencia.petrobras.com.br/w/resultado"
    d = ingerir_link(url, indice, CFG, cliente({url: (200, "text/html; charset=utf-8", HTML)}))
    assert d.titulo == "Copom eleva a Selic"
    assert "Selic" in d.texto and "menu" not in d.texto and "rodapé" not in d.texto
    assert d.proveniencia.tipo == "link" and d.proveniencia.url == url


def test_link_para_pdf_usa_o_adaptador_de_pdf(indice):
    url = "https://www.bcb.gov.br/content/copom/ata.pdf"
    dados = pdf_minimo([TEXTO_FINANCEIRO * 2])
    d = ingerir_link(url, indice, CFG, cliente({url: (200, "application/pdf", dados)}))
    assert d.paginas == 1 and d.proveniencia.tipo == "link"
    assert d.proveniencia.sha256_bruto == documento.sha256_bytes(dados)


def test_dominio_nao_permitido_nem_chega_a_baixar(indice):
    chamadas = []
    with pytest.raises(ErroIngestao, match="fontes permitidas"):
        ingerir_link("https://exemplo.com/a", indice, CFG, cliente({}, chamadas))
    assert chamadas == []


def test_redirecionamento_para_fora_e_bloqueado(indice):
    url = "https://www.bcb.gov.br/a"
    c = cliente({url: (302, "text/html", b"", "https://exemplo.com/b")})
    with pytest.raises(ErroIngestao, match="fontes permitidas"):
        ingerir_link(url, indice, CFG, c)


def test_redirecionamento_dentro_do_permitido_funciona(indice):
    a, b = "https://www.bcb.gov.br/a", "https://www.bcb.gov.br/b"
    c = cliente({a: (301, "text/html", b"", b), b: (200, "text/html", HTML)})
    assert ingerir_link(a, indice, CFG, c).proveniencia.url == b


def test_erro_http_vira_erro_de_ingestao(indice):
    url = "https://www.bcb.gov.br/nada"
    with pytest.raises(ErroIngestao, match="404"):
        ingerir_link(url, indice, CFG, cliente({}))


def test_arquivo_grande_demais(indice):
    import copy
    cfg = copy.deepcopy(CFG)
    cfg["link"]["tamanho_maximo_mb"] = 0.001
    url = "https://www.bcb.gov.br/a"
    with pytest.raises(ErroIngestao, match="passa de"):
        ingerir_link(url, indice, cfg, cliente({url: (200, "text/html", HTML)}))


def test_tipo_de_conteudo_estranho(indice):
    url = "https://www.bcb.gov.br/a.zip"
    with pytest.raises(ErroIngestao, match="nem um PDF"):
        ingerir_link(url, indice, CFG, cliente({url: (200, "application/zip", b"PK\x03\x04" + b"0" * 100)}))


def test_pagina_que_nao_e_financeira(indice):
    url = "https://www.bcb.gov.br/a"
    html = ("<html><body><main>" + "<p>O bolo de chocolate leva farinha, ovos, leite e açúcar e vai ao forno por quarenta minutos.</p>" * 8
            + "</main></body></html>").encode()
    with pytest.raises(ErroIngestao, match="não parece financeira"):
        ingerir_link(url, indice, CFG, cliente({url: (200, "text/html", html)}))


# ---------- termo ----------

def test_normalizar_termo():
    assert termo.normalizar("  Inflação!! ") == "inflacao"
    assert termo.normalizar("Taxa  Selic?") == "taxa selic"


def test_canonico_pelo_glossario(indice):
    assert termo.canonico("taxa Selic", indice) == "Selic"
    assert termo.canonico("Selic", indice) == "Selic"
    assert termo.canonico("banana", indice) is None


ATAS = '{"conteudo":[{"nroReuniao":280,"dataReferencia":"2026-08-05"},{"nroReuniao":281,"dataReferencia":"2026-09-16"}]}'
URL_ATA = "https://www.bcb.gov.br/content/copom/atascopom/Copom281-not20260916281.pdf"
API_ATAS = CFG["fontes_periodicas"]["ata_copom_recente"]["api"]


def test_termo_resolve_para_a_ata_mais_recente(indice):
    c = cliente({API_ATAS: (200, "application/json", ATAS.encode())})
    r = termo.resolver("Selic", indice, CFG, c)
    assert r.url == URL_ATA and r.termo_canonico == "Selic" and r.termo_normalizado == "selic"


def test_termo_resolve_pelo_sinonimo_do_glossario(indice):
    c = cliente({API_ATAS: (200, "application/json", ATAS.encode())})
    assert termo.resolver("taxa básica de juros", indice, CFG, c).url == URL_ATA


def test_termo_periodico_pega_o_primeiro_que_existe(indice):
    url = "https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606p.pdf"
    c = cliente({url: (200, "application/pdf", b"")})
    r = termo.resolver("inflação", indice, CFG, c, hoje=date(2026, 10, 9))
    assert r.url == url


def test_termo_periodico_ignora_meses_futuros(indice):
    chamadas = []
    c = cliente({}, chamadas)
    with pytest.raises(ErroIngestao, match="localizar"):
        termo.resolver("inflação", indice, CFG, c, hoje=date(2026, 5, 1))
    assert not any("202609" in u or "202612" in u for _, u in chamadas)


def test_termo_com_url_fixa(indice):
    r = termo.resolver("fundos de investimento", indice, CFG, cliente({}))
    assert r.url.endswith("resol175consolid_ParteGeral.pdf")


def test_termo_desconhecido_e_termo_curto(indice):
    with pytest.raises(ErroIngestao, match="Não há fonte"):
        termo.resolver("banana", indice, CFG, cliente({}))
    with pytest.raises(ErroIngestao, match="duas letras"):
        termo.resolver("a", indice, CFG, cliente({}))


def test_ingerir_termo_registra_termo_e_url(indice):
    dados = pdf_minimo([TEXTO_FINANCEIRO * 2])
    c = cliente({API_ATAS: (200, "application/json", ATAS.encode()), URL_ATA: (200, "application/pdf", dados)})
    d = ingerir_termo("taxa Selic", indice, CFG, c)
    p = d.proveniencia
    assert p.tipo == "termo" and p.url == URL_ATA and p.origem == "taxa Selic"     # a origem é o que foi pesquisado
    assert p.documento == "Ata da 281ª reunião do Copom (16/09/2026)"
    assert p.sha256_bruto == documento.sha256_bytes(dados)


def test_termo_periodico_tem_nome_do_documento(indice):
    url = "https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606p.pdf"
    r = termo.resolver("inflação", indice, CFG, cliente({url: (200, "application/pdf", b"")}), hoje=date(2026, 10, 9))
    assert r.documento == "Relatório de Política Monetária de 06/2026"
    assert termo.resolver("fundos de investimento", indice, CFG, cliente({})).documento == "Resolução CVM 175 (fundos de investimento)"


def test_ata_recente_tenta_de_novo_quando_a_api_falha(monkeypatch):
    monkeypatch.setattr(termo.time, "sleep", lambda s: None)
    chamadas = {"n": 0}

    def tratar(req):
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise httpx.ConnectTimeout("lento")
        return httpx.Response(200, json=__import__("json").loads(ATAS))

    c = httpx.Client(transport=httpx.MockTransport(tratar))
    assert termo._ata_recente(CFG["fontes_periodicas"]["ata_copom_recente"], c) == URL_ATA and chamadas["n"] == 3


def test_ata_recente_desiste_depois_das_tentativas(monkeypatch):
    monkeypatch.setattr(termo.time, "sleep", lambda s: None)
    c = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(500)))
    assert termo._ata_recente(CFG["fontes_periodicas"]["ata_copom_recente"], c) is None
