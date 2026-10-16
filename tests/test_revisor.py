import inspect

import pytest

from avaliador import avaliar as av
from avaliador import glossario
from geracao import grafo, revisor
from geracao.ramo import construir_ramo, rodar_ramo
from tests.fixtures_geracao import ANCORA, GeradorFalso, JuizFalso


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


@pytest.fixture()
def cfg():
    c = av.carregar_config()
    c["formatos"]["artigo"]["palavras"] = [20, 900]
    return c


class RevisorFalso:
    def __init__(self):
        self.pedidos = []

    def completar_json(self, sistema, usuario, schema):
        self.pedidos.append(usuario)
        return {"diagnostico": "Usou jargao sem explicar.",
                "acoes": ["No corpo, explique a Selic: a taxa basica de juros da economia.", "  ", "Inclua o fato f1 com 14,25."],
                "manter": ["O numero 5,06 ja esta correto."]}


class RevisorQuebrado:
    def completar_json(self, *a):
        raise RuntimeError("fora do ar")


def _ramo(indice, cfg, gerador, rev, max_t=2):
    return construir_ramo(gerador, JuizFalso(), indice, cfg, max_t, tentativas_juiz=1, espera_juiz_s=0, revisor=rev)


def test_o_limite_padrao_e_de_duas_tentativas():
    assert inspect.signature(construir_ramo).parameters["max_tentativas"].default == 2
    assert inspect.signature(grafo.construir_grafo).parameters["max_tentativas"].default == 2
    assert inspect.signature(grafo.processar).parameters["max_tentativas"].default == 2


def test_plano_limpa_acoes_vazias_e_traz_explicacao_do_termo():
    rev = RevisorFalso()
    termos = [glossario.Termo("Selic", 2, "juros", ("Selic",), False, "a taxa basica de juros da economia")]
    plano = revisor.planejar(rev, "iniciante", "artigo", ANCORA, "texto antigo",
                             ["[glossario] termo de nivel 2 sem explicacao: 'Selic' em \"...\""], termos)
    assert len(plano.acoes) == 2 and plano.manter == ["O numero 5,06 ja esta correto."]
    assert "Selic: a taxa basica de juros da economia" in rev.pedidos[0]
    assert "texto antigo" in rev.pedidos[0] and "[f1]" in rev.pedidos[0]


def test_plano_vai_para_o_prompt_da_proxima_tentativa_e_fica_registrado(indice, cfg):
    gerador, rev = GeradorFalso(1), RevisorFalso()
    r = rodar_ramo(_ramo(indice, cfg, gerador, rev), "iniciante", "artigo", ANCORA)
    assert r.status == "aprovado" and len(r.tentativas) == 2
    assert len(rev.pedidos) == 1                                    # só revisa quando vai haver outra tentativa
    segundo_prompt = gerador.prompts[1][1]
    assert "PLANO DO REVISOR" in segundo_prompt and "Usou jargao sem explicar." in segundo_prompt
    assert "MANTENHA" in segundo_prompt
    plano = r.tentativas[0].metricas["plano_revisao"]
    assert plano["diagnostico"] == "Usou jargao sem explicar." and len(plano["acoes"]) == 2
    assert "plano_revisao" not in r.tentativas[1].metricas
    assert r.tentativas[0].chamadas_llm == 2                        # geração + revisão (juiz não rodou: regras reprovaram)


def test_se_o_revisor_falha_a_reescrita_segue_sem_plano(indice, cfg):
    gerador = GeradorFalso(1)
    r = rodar_ramo(_ramo(indice, cfg, gerador, RevisorQuebrado()), "iniciante", "artigo", ANCORA)
    assert r.status == "aprovado" and len(r.tentativas) == 2
    assert "PLANO DO REVISOR" not in gerador.prompts[1][1]
    assert "plano_revisao" not in r.tentativas[0].metricas


def test_sem_revisor_o_comportamento_continua_igual(indice, cfg):
    gerador = GeradorFalso(1)
    r = rodar_ramo(_ramo(indice, cfg, gerador, None), "iniciante", "artigo", ANCORA)
    assert r.status == "aprovado" and "PLANO DO REVISOR" not in gerador.prompts[1][1]


def test_com_duas_tentativas_o_ramo_bloqueia_e_nao_revisa_depois_da_ultima(indice, cfg):
    rev = RevisorFalso()
    r = rodar_ramo(_ramo(indice, cfg, GeradorFalso(99), rev), "iniciante", "artigo", ANCORA)
    assert r.status == "bloqueado" and len(r.tentativas) == 2
    assert len(rev.pedidos) == 1
