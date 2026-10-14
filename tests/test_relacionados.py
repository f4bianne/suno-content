import pytest

from armazenamento.repositorio import Repositorio
from armazenamento.servico import processar_com_banco
from avaliador import avaliar as av
from avaliador import glossario
from geracao import grafo
from ingestao.documento import Documento, Proveniencia
from tests.fixtures_geracao import GeradorFalso, JuizFalso
from tests.test_api import TEXTO


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


@pytest.fixture()
def cfg():
    c = av.carregar_config()
    c["formatos"]["artigo"]["palavras"] = [20, 900]
    return c


class ExtratorComEntidades:
    """Devolve um fato cujas entidades são as informadas, para controlar a afinidade entre documentos."""

    def __init__(self, entidades: list[str]):
        self.entidades, self.modelo = entidades, "extrator-x"

    def completar_json(self, sistema, usuario, schema):
        return {"fatos": [{"texto": "O Copom elevou a Selic para 14,25% ao ano", "numeros": ["14,25"], "entidades": self.entidades,
                           "trecho_origem": "O Copom elevou a Selic para 14,25% ao ano em março"}]}


def gerar(repo, indice, cfg, entidades, extra="", tipo="termo", sessao=None, origem="doc", modelo="m"):
    d = Documento(texto=TEXTO + extra, proveniencia=Proveniencia(tipo=tipo, origem=origem, sha256_bruto="0" * 64))
    g = GeradorFalso(0)
    g.modelo = modelo
    cl = grafo.Clientes(extrator=ExtratorComEntidades(entidades), gerador=g, juiz=JuizFalso())
    return processar_com_banco(d, cl, indice, repo, cfg, niveis=("iniciante",), formatos=("artigo",), sessao=sessao)


def test_acha_documentos_que_falam_das_mesmas_coisas(indice, cfg):
    repo = Repositorio("sqlite://")
    a = gerar(repo, indice, cfg, ["Selic", "Copom"], origem="ata")
    b = gerar(repo, indice, cfg, ["Selic", "IPCA"], extra=" B", origem="relatorio")
    gerar(repo, indice, cfg, ["Dividendos"], extra=" C", origem="outro assunto")
    rel = repo.relacionados(a.execucao_id)
    assert [r["origem"] for r in rel] == ["relatorio"]
    assert rel[0]["entidades_comuns"] == ["Selic"] and rel[0]["id"] == b.execucao_id
    # O extrator descarta entidades que não estão no trecho citado (IPCA não está), então ficam {Selic} e {Selic, Copom}.
    assert rel[0]["afinidade"] == pytest.approx(1 / 2)


def test_ordena_por_afinidade_e_nao_repete_documento(indice, cfg):
    repo = Repositorio("sqlite://")
    a = gerar(repo, indice, cfg, ["Selic", "Copom", "IPCA"], origem="alvo")
    gerar(repo, indice, cfg, ["Selic", "Copom", "IPCA"], extra=" B", origem="quase igual")
    gerar(repo, indice, cfg, ["Selic", "X", "Y", "Z"], extra=" C", origem="pouco parecido")
    gerar(repo, indice, cfg, ["Selic", "Copom", "IPCA"], extra=" B", origem="quase igual", modelo="outro")   # 2a versão do mesmo documento
    assert [r["origem"] for r in repo.relacionados(a.execucao_id)] == ["quase igual", "pouco parecido"]


def test_ignora_maiuscula_e_respeita_limite_e_privacidade(indice, cfg):
    repo = Repositorio("sqlite://")
    a = gerar(repo, indice, cfg, ["SELIC"], origem="alvo")
    gerar(repo, indice, cfg, ["selic"], extra=" B", origem="publico")
    gerar(repo, indice, cfg, ["Selic"], extra=" C", tipo="pdf", sessao="ana", origem="privado.pdf")
    assert [r["origem"] for r in repo.relacionados(a.execucao_id)] == ["publico"]
    assert {r["origem"] for r in repo.relacionados(a.execucao_id, sessao="ana")} == {"publico", "privado.pdf"}
    assert len(repo.relacionados(a.execucao_id, sessao="ana", limite=1)) == 1


def test_execucao_inexistente_e_sem_entidades(indice, cfg):
    repo = Repositorio("sqlite://")
    assert repo.relacionados("nada") == []
    a = gerar(repo, indice, cfg, [], origem="sem entidades")
    gerar(repo, indice, cfg, ["Selic"], extra=" B", origem="outro")
    assert repo.relacionados(a.execucao_id) == []


def test_lista_de_execucoes_traz_o_identificador_do_documento(indice, cfg):
    repo = Repositorio("sqlite://")
    a = gerar(repo, indice, cfg, ["Selic"])
    item = repo.listar()[0]
    assert item["id"] == a.execucao_id and len(item["documento"]) == 64
