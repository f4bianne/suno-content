import pytest

from ingestao import extrator
from ingestao.documento import Documento, Proveniencia

TEXTO = (
    "O Comitê de Política Monetária (Copom) elevou a taxa Selic para 14,25% ao ano na reunião de março.\n"
    "A inflação em 12 meses medida pelo IPCA subiu de 4,87% para 5,06% em fevereiro de 2025.\n"
    "O Comitê vê o cenário externo com elevada incerteza e riscos assimétricos para a inflação.\n"
)


def doc(texto=TEXTO):
    return Documento(texto=texto, proveniencia=Proveniencia(tipo="pdf", origem="a.pdf", sha256_bruto="0" * 64))


class ClienteFalso:
    def __init__(self, respostas):
        self.respostas, self.chamadas = list(respostas), 0

    def completar_json(self, sistema, usuario, schema):
        self.chamadas += 1
        return self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]


def fato(texto, numeros, entidades, trecho):
    return {"texto": texto, "numeros": numeros, "entidades": entidades, "trecho_origem": trecho}


BOM = fato("O Copom elevou a Selic para 14,25% ao ano", ["14,25"], ["Copom", "Selic"],
           "elevou a taxa Selic para 14,25% ao ano na reunião de março")


def test_fato_valido_entra_na_ancora_com_id():
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [BOM]}]), doc())
    assert [f.id for f in r.ancora.fatos] == ["f1"]
    assert r.ancora.fatos[0].numeros == ["14,25"] and r.descartados == []


def test_trecho_inventado_e_descartado():
    inventado = fato("A Selic vai a 20%", ["20"], ["Selic"], "o Copom projeta a Selic de 20% até dezembro de 2026")
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [inventado, BOM]}]), doc())
    assert len(r.ancora.fatos) == 1
    assert r.descartados[0][0] == "trecho de origem não existe no documento"


def test_numero_fora_do_trecho_e_descartado():
    errado = fato("A Selic subiu para 15%", ["15"], ["Selic"], "elevou a taxa Selic para 14,25% ao ano na reunião de março")
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [errado]}]), doc())
    assert r.ancora.fatos == [] and "número 15" in r.descartados[0][0]


def test_trecho_curto_demais_e_descartado():
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [fato("x", [], [], "Selic")]}]), doc())
    assert r.ancora.fatos == []


def test_entidade_fora_do_trecho_e_removida_mas_o_fato_fica():
    f = fato("O Copom elevou a Selic", ["14,25"], ["Copom", "Fed"], "elevou a taxa Selic para 14,25% ao ano na reunião de março")
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [f]}]), doc())
    assert r.ancora.fatos[0].entidades == []   # "Copom" não está nesse trecho


def test_repeticao_e_ignorada_e_trecho_com_quebra_de_linha_vale():
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [BOM, BOM]}]), doc())
    assert len(r.ancora.fatos) == 1 and r.descartados[0][0] == "fato repetido"
    quebrado = TEXTO.replace("elevou a taxa Selic", "elevou a\ntaxa Selic")
    assert len(extrator.extrair_ancora(ClienteFalso([{"fatos": [BOM]}]), doc(quebrado)).ancora.fatos) == 1


def test_limite_de_fatos_prioriza_numero_e_entidade():
    sem_numero = fato("O comitê vê incerteza", [], [], "vê o cenário externo com elevada incerteza e riscos assimétricos")
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [sem_numero, BOM]}]), doc(), max_fatos=1)
    assert r.ancora.fatos[0].numeros == ["14,25"]


def test_documento_longo_e_dividido_e_limitado():
    longo = "\n".join(f"Linha {i} sobre juros e inflação sem números relevantes aqui." for i in range(2000))
    c = ClienteFalso([{"fatos": []}])
    r = extrator.extrair_ancora(c, doc(longo), max_pedacos=3, tamanho_pedaco=2000)
    assert c.chamadas == r.chamadas == 3


def test_pedacos_mais_numericos_sao_preferidos():
    pedacos = ["texto sem numero", "1 2 3 4 5 6 7 8 9", "outro sem numero", "10 20 30 40 50"]
    assert extrator.escolher(pedacos, 2) == ["1 2 3 4 5 6 7 8 9", "10 20 30 40 50"]


def test_schema_para_llm_e_plano_e_estrito():
    from avaliador.juiz import schema_plano
    s = schema_plano(extrator.LoteFatos)
    assert "$ref" not in str(s) and "$defs" not in str(s)
    fato_schema = s["properties"]["fatos"]["items"]
    assert fato_schema["additionalProperties"] is False
    assert set(fato_schema["required"]) == {"texto", "numeros", "entidades", "trecho_origem"}


def test_cliente_anthropic_exige_chave(monkeypatch):
    from ingestao import clientes
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(clientes, "ler_env", lambda nome: None)
    with pytest.raises(RuntimeError):
        clientes.ClienteAnthropic()


def test_cliente_gemini_monta_a_requisicao_e_le_a_resposta(monkeypatch):
    import httpx

    from ingestao import clientes
    visto = {}

    def falso_post(url, json=None, headers=None, timeout=None):
        visto.update(url=url, corpo=json, headers=headers)
        return httpx.Response(200, request=httpx.Request("POST", url), json={"candidates": [{"content": {"parts": [
            {"text": "pensando", "thought": True}, {"text": '{"fatos": []}'}]}}]})

    monkeypatch.setattr(httpx, "post", falso_post)
    c = clientes.ClienteGemini(chave="k", modelo="m1")
    assert c.completar_json("sis", "usu", {"type": "object"}) == {"fatos": []}
    assert visto["url"].endswith("/models/m1:generateContent") and visto["headers"] == {"x-goog-api-key": "k"}
    assert visto["corpo"]["generationConfig"]["responseMimeType"] == "application/json"
    assert visto["corpo"]["systemInstruction"]["parts"][0]["text"] == "sis"


def test_cliente_gemini_exige_chave(monkeypatch):
    from ingestao import clientes
    monkeypatch.setattr(clientes, "ler_env", lambda nome: None)
    with pytest.raises(RuntimeError):
        clientes.ClienteGemini()


def test_numero_com_simbolo_e_limpo_e_aceito():
    f = fato("O Copom elevou a Selic", ["14,25%"], ["Selic"], "elevou a taxa Selic para 14,25% ao ano na reunião de março")
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [f]}]), doc())
    assert r.ancora.fatos[0].numeros == ["14,25"] and r.descartados == []


def test_numero_com_simbolo_mas_inexistente_continua_descartado():
    f = fato("A Selic foi a 15%", ["R$ 15"], ["Selic"], "elevou a taxa Selic para 14,25% ao ano na reunião de março")
    r = extrator.extrair_ancora(ClienteFalso([{"fatos": [f]}]), doc())
    assert r.ancora.fatos == []


def test_pedaco_que_falha_nao_derruba_o_documento():
    class Instavel:
        n = 0

        def completar_json(self, sistema, usuario, schema):
            self.n += 1
            if self.n == 1:
                raise RuntimeError("fora do ar")
            return {"fatos": [BOM]}

    longo = TEXTO + "\n".join(f"Linha {i} de enchimento sobre juros e inflação." for i in range(400))
    r = extrator.extrair_ancora(Instavel(), doc(longo), tamanho_pedaco=2000, max_pedacos=2)
    assert len(r.ancora.fatos) == 1 and "pedaço do documento falhou" in r.descartados[0][0]
