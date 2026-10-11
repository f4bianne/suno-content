import time

import pytest
from fastapi.testclient import TestClient

from api.main import criar_app
from avaliador import avaliar as av
from geracao import grafo
from ingestao.documento import Documento, ErroIngestao, Proveniencia
from tests.fixtures_geracao import GeradorFalso, JuizFalso

TEXTO = ("O Copom elevou a Selic para 14,25% ao ano em março. A inflação em 12 meses medida pelo IPCA foi de 5,06% em fevereiro. "
         "O comitê vê incerteza elevada no cenário externo.")


class ExtratorFalso:
    def completar_json(self, sistema, usuario, schema):
        return {"fatos": [
            {"texto": "O Copom elevou a Selic para 14,25% ao ano", "numeros": ["14,25"], "entidades": ["Selic"],
             "trecho_origem": "O Copom elevou a Selic para 14,25% ao ano em março"},
            {"texto": "A inflação em 12 meses medida pelo IPCA foi de 5,06%", "numeros": ["5,06"], "entidades": ["IPCA"],
             "trecho_origem": "A inflação em 12 meses medida pelo IPCA foi de 5,06% em fevereiro"},
            {"texto": "O comitê vê incerteza elevada no cenário externo", "numeros": [], "entidades": [],
             "trecho_origem": "O comitê vê incerteza elevada no cenário externo"},
        ]}


def ingestor_falso(tipo, valor, nome, indice):
    if tipo == "termo" and valor == "quebrado":
        raise ErroIngestao("Não há fonte oficial cadastrada para \"quebrado\".")
    origem = nome if tipo == "pdf" else valor
    return Documento(texto=TEXTO, paginas=1 if tipo == "pdf" else None,
                     proveniencia=Proveniencia(tipo="link" if tipo == "pdf" else tipo, origem=origem, sha256_bruto="0" * 64))


@pytest.fixture()
def cliente(tmp_path):
    cfg = av.carregar_config()
    cfg["formatos"]["artigo"]["palavras"] = [20, 900]
    app = criar_app(
        fabrica_clientes=lambda: grafo.Clientes(extrator=ExtratorFalso(), gerador=GeradorFalso(0), juiz=JuizFalso()),
        ingestor=ingestor_falso, pasta_saidas=tmp_path / "saidas", cfg=cfg)
    return TestClient(app)


def esperar(c, job_id, ate=30):
    for _ in range(int(ate / 0.2)):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("concluido", "erro"):
            return j
        time.sleep(0.2)
    raise AssertionError("job não terminou")


def test_job_de_termo_gera_os_nove_ramos(cliente):
    r = cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom"})
    assert r.status_code == 200
    j = esperar(cliente, r.json()["id"])
    assert j["status"] == "concluido" and j["erro"] is None
    assert len(j["resultado"]["ramos"]) == 9
    assert {e["tipo"] for e in j["eventos"]} >= {"ingerindo", "documento", "extraindo", "ancora", "gerando", "avaliado", "ramo_fim", "fim"}
    assert [f["id"] for f in j["resultado"]["ancora"]["fatos"]] == ["f1", "f2", "f3"]


def test_historico_lista_e_abre_a_execucao(cliente):
    esperar(cliente, cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom"}).json()["id"])
    lista = cliente.get("/api/execucoes").json()
    assert len(lista) == 1 and lista[0]["ramos"] == 9 and lista[0]["aprovados"] == 9 and lista[0]["origem"] == "Copom"
    d = cliente.get(f"/api/execucoes/{lista[0]['chave']}").json()
    assert len(d["ramos"]) == 9 and "gerado_em" in d


def test_execucao_inexistente_e_sem_escapar_da_pasta(cliente):
    assert cliente.get("/api/execucoes/nao_existe").status_code == 404
    assert cliente.get("/api/execucoes/..%2F..%2Frequirements").status_code == 404


def test_erro_de_ingestao_vira_job_com_mensagem(cliente):
    j = esperar(cliente, cliente.post("/api/jobs", json={"tipo": "termo", "valor": "quebrado"}).json()["id"])
    assert j["status"] == "erro" and "Não há fonte" in j["erro"] and j["resultado"] is None
    assert j["eventos"][-1]["tipo"] == "erro"


def test_pdf_enviado_como_corpo_binario(cliente):
    r = cliente.post("/api/jobs/pdf?nome=ata.pdf&niveis=iniciante&formatos=artigo", content=b"%PDF-1.4 fake")
    j = esperar(cliente, r.json()["id"])
    assert j["status"] == "concluido" and j["entrada"] == {"tipo": "pdf", "valor": "ata.pdf"}
    assert [(x["nivel"], x["formato"]) for x in j["resultado"]["ramos"]] == [("iniciante", "artigo")]


def test_recorte_de_niveis_e_formatos(cliente):
    r = cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom", "niveis": ["avancado"], "formatos": ["video"]})
    j = esperar(cliente, r.json()["id"])
    assert [(x["nivel"], x["formato"]) for x in j["resultado"]["ramos"]] == [("avancado", "video")]


@pytest.mark.parametrize("corpo", [
    {"tipo": "termo", "valor": "   "},
    {"tipo": "termo", "valor": "x", "niveis": ["expert"]},
    {"tipo": "termo", "valor": "x", "formatos": ["podcast"]},
    {"tipo": "ftp", "valor": "x"},
])
def test_pedidos_invalidos_sao_recusados(cliente, corpo):
    assert cliente.post("/api/jobs", json=corpo).status_code == 422


def test_job_inexistente(cliente):
    assert cliente.get("/api/jobs/zzz").status_code == 404
    assert cliente.get("/api/jobs/zzz/eventos").status_code == 404


def test_eventos_em_sse_terminam_com_fim(cliente):
    jid = cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom", "niveis": ["iniciante"], "formatos": ["artigo"]}).json()["id"]
    with cliente.stream("GET", f"/api/jobs/{jid}/eventos") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        linhas = [l for l in r.iter_lines() if l.startswith("data: ")]
    assert '"tipo": "fim"' in linhas[-1] and any('"tipo": "ramo_fim"' in l for l in linhas)


def test_config_expoe_limiares(cliente):
    c = cliente.get("/api/config").json()
    assert c["niveis"] == ["iniciante", "intermediario", "avancado"] and "flesch" in c["limiares"]["iniciante"]


def test_sem_chave_o_job_falha_com_mensagem_clara(tmp_path, monkeypatch):
    from api import main

    def sem_chave():
        raise RuntimeError("defina GROQ_API_KEY no ambiente")

    app = criar_app(fabrica_clientes=sem_chave, ingestor=ingestor_falso, pasta_saidas=tmp_path)
    c = TestClient(app)
    j = esperar(c, c.post("/api/jobs", json={"tipo": "termo", "valor": "Copom"}).json()["id"])
    assert j["status"] == "erro" and "GROQ_API_KEY" in j["erro"]


def test_execucoes_do_mesmo_documento_nao_se_sobrescrevem(cliente):
    esperar(cliente, cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom", "niveis": ["iniciante"], "formatos": ["artigo"]}).json()["id"])
    time.sleep(1.1)   # o nome inclui segundos
    esperar(cliente, cliente.post("/api/jobs", json={"tipo": "termo", "valor": "Copom"}).json()["id"])
    lista = cliente.get("/api/execucoes").json()
    assert len(lista) == 2 and {x["ramos"] for x in lista} == {1, 9}
