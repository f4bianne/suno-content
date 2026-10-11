import httpx
import pytest

from armazenamento import monitor
from armazenamento.repositorio import Repositorio
from armazenamento.servico import processar_com_banco
from avaliador import avaliar as av
from avaliador import glossario
from ingestao.documento import Documento, Proveniencia, carregar_config
from tests.test_api import TEXTO
from tests.test_armazenamento import clientes

CFG = carregar_config()
API = CFG["fontes_periodicas"]["ata_copom_recente"]["api"]
ATAS = {"conteudo": [{"nroReuniao": 281, "dataReferencia": "2026-09-16"}]}
URL_ATA = "https://www.bcb.gov.br/content/copom/atascopom/Copom281-not20260916281.pdf"


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


def http():
    def tratar(req: httpx.Request) -> httpx.Response:
        if str(req.url) == API:
            return httpx.Response(200, json=ATAS)
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(tratar))


def por_nome(fontes):
    return {f.nome: f for f in fontes}


def test_fonte_nova_e_detectada(indice):
    f = por_nome(monitor.verificar(Repositorio("sqlite://"), indice, CFG, http()))["ata do Copom mais recente"]
    assert f.url == URL_ATA and f.nova and f.erro is None


def test_fonte_ja_processada_nao_e_nova(indice):
    repo = Repositorio("sqlite://")
    doc = Documento(texto=TEXTO, proveniencia=Proveniencia(tipo="link", origem=URL_ATA, url=URL_ATA, sha256_bruto="0" * 64))
    cfg = av.carregar_config()
    cfg["formatos"]["artigo"]["palavras"] = [20, 900]
    processar_com_banco(doc, clientes(), indice, repo, cfg, niveis=("iniciante",), formatos=("artigo",))
    f = por_nome(monitor.verificar(repo, indice, CFG, http()))["ata do Copom mais recente"]
    assert f.url == URL_ATA and not f.nova


def test_fonte_nao_localizada_vira_erro_sem_derrubar_as_outras(indice):
    fontes = por_nome(monitor.verificar(Repositorio("sqlite://"), indice, CFG, http()))
    rpm = fontes["Relatório de Política Monetária mais recente"]
    assert rpm.url is None and rpm.erro and not rpm.nova
    assert fontes["Resolução CVM 175 (fundos de investimento)"].nova   # URL fixa é nova na primeira vez
