"""Gráficos opcionais no carrossel: limites de formato, números conferidos, schema do gerador e opção na API."""
import copy

import pytest
from fastapi.testclient import TestClient

from avaliador import avaliar as av
from avaliador import glossario
from avaliador.formatos import Carrossel, Grafico, numero_br, texto_dos_graficos, verificar
from geracao import ajustes, prompts, schemas
from tests.fixtures_geracao import ANCORA
from tests.test_api import cliente, esperar  # noqa: F401  (cliente é fixture)


@pytest.fixture(scope="module")
def cfg():
    return av.carregar_config()


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


def grafico(**kw):
    base = dict(slide=1, tipo="barras", titulo="Selic e IPCA", rotulos=["Selic", "IPCA"], valores=[14.25, 5.06], unidade="%")
    return Grafico(**{**base, **kw})


SLIDES = ["Gancho curto.", "A Selic subiu e a inflação também.", "Lá fora, a incerteza segue alta.", "O comitê segue atento.",
          "Conclusão curta."]


def test_numero_no_jeito_dos_fatos():
    assert [numero_br(v) for v in (4.9, 14.25, 5216, -0.5, 15.0)] == ["4,9", "14,25", "5.216", "-0,5", "15"]


def test_grafico_valido_passa(cfg):
    assert verificar(Carrossel(slides=SLIDES, graficos=[grafico()]), cfg["formatos"]) == []


@pytest.mark.parametrize("g, trecho", [
    (dict(slide=0), "o gancho e a conclusão não levam gráfico"),
    (dict(slide=4), "o gancho e a conclusão não levam gráfico"),
    (dict(slide=9), "não existe"),
    (dict(rotulos=["a"]), "1 rótulos para 2 valores"),
    (dict(rotulos=["a"], valores=[1.0]), "1 pontos (esperado de 2 a 6)"),
    (dict(rotulos=list("abcdefg"), valores=[1.0] * 7), "7 pontos"),
    (dict(titulo="x" * 60), "título com 60 caracteres"),
    (dict(rotulos=["um rótulo comprido demais", "b"]), "rótulo 'um rótulo comprido demais'"),
    (dict(unidade="bilhões de reais"), "unidade 'bilhões de reais' longa demais"),
])
def test_limites_do_grafico(cfg, g, trecho):
    falhas = verificar(Carrossel(slides=SLIDES, graficos=[grafico(**g)]), cfg["formatos"])
    assert any(trecho in f for f in falhas), falhas


def test_slide_com_grafico_tem_menos_texto_e_um_grafico_so(cfg):
    slides = [*SLIDES]
    slides[1] = "x" * 130
    falhas = verificar(Carrossel(slides=slides, graficos=[grafico(), grafico()]), cfg["formatos"])
    assert any("slide 2 com gráfico tem 130 caracteres de texto (máximo 120)" in f for f in falhas)
    assert any("slide 2 com mais de um gráfico" in f for f in falhas)
    tres = [grafico(slide=i) for i in (1, 2, 3)]
    assert any("3 gráficos (máximo 2)" in f for f in verificar(Carrossel(slides=SLIDES, graficos=tres), cfg["formatos"]))


def test_numero_do_grafico_e_conferido_contra_a_ancora(cfg, indice):
    ok = av.avaliar(Carrossel(slides=SLIDES, graficos=[grafico()]), "avancado", indice, ANCORA, cfg)
    assert not [f for f in ok.falhas if f.metrica == "numeros"]
    inventado = av.avaliar(Carrossel(slides=SLIDES, graficos=[grafico(valores=[14.25, 6.1])]), "avancado", indice, ANCORA, cfg)
    assert [f.mensagem for f in inventado.falhas if f.metrica == "numeros"] == ["gráfico traz o número '6,1', que não existe na âncora"]
    assert "Selic 14,25%; IPCA 5,06%" in texto_dos_graficos(Carrossel(slides=SLIDES, graficos=[grafico()]))


def test_schema_e_prompt_so_mudam_quando_a_pessoa_pede(cfg):
    assert schemas.schema_de("carrossel", cfg) is schemas.CarrosselLLM
    assert "GRÁFICOS" not in prompts.instrucao_formato("carrossel", cfg)
    com = copy.deepcopy(cfg)
    com["formatos"]["carrossel"]["graficos"] = True
    assert schemas.schema_de("carrossel", com) is schemas.CarrosselComGraficosLLM
    assert schemas.schema_de("artigo", com) is schemas.ArtigoLLM
    assert "GRÁFICOS" in prompts.instrucao_formato("carrossel", com)


def test_resposta_do_gerador_vira_grafico_no_slide_certo():
    c = schemas.para_conteudo("carrossel", {
        "gancho": "G", "slides_corpo": ["A", "B"], "conclusao": "C",
        "graficos": [{"slide_corpo": 2, "tipo": "linha", "titulo": "T", "rotulos": ["2026", "2027"], "valores": [4.9, 4.3], "unidade": "%"}],
    })
    assert c.slides == ["G", "A", "B", "C"] and c.graficos[0].slide == 2 and c.slides[c.graficos[0].slide] == "B"
    assert schemas.para_conteudo("carrossel", {"gancho": "G", "slides_corpo": ["A"], "conclusao": "C"}).graficos == []


def test_relatorio_de_falhas_mostra_os_graficos_anteriores():
    rel = prompts.relatorio_de_falhas(["[formato] x"], Carrossel(slides=SLIDES, graficos=[grafico()]))
    assert "GRÁFICOS DA VERSÃO ANTERIOR" in rel and "Selic = 14,25%" in rel


def test_ajuste_de_termos_mantem_o_grafico(cfg, indice):
    c = Carrossel(slides=SLIDES, graficos=[grafico()])
    novo, _ = ajustes.explicar_termos(c, "iniciante", indice, cfg)
    assert novo.graficos == c.graficos


def test_api_gera_carrossel_com_grafico_sem_misturar_com_o_cache(cliente):
    sem = esperar(cliente, cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom", "formatos": ["carrossel"]}).json()["id"])
    com = esperar(cliente, cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom", "formatos": ["carrossel"],
                                                           "graficos": True}).json()["id"])
    assert com["resultado"]["do_cache"] is False                       # com gráfico é outra configuração
    assert all(r["conteudo"]["graficos"] == [] for r in sem["resultado"]["ramos"])
    ramos = com["resultado"]["ramos"]
    assert all(r["status"] == "aprovado" and len(r["conteudo"]["graficos"]) == 1 for r in ramos)
    de_novo = esperar(cliente, cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom", "formatos": ["carrossel"],
                                                               "graficos": True}).json()["id"])
    assert de_novo["resultado"]["do_cache"] is True
