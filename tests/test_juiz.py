import pytest
from pydantic import ValidationError

from avaliador import classificador, juiz
from avaliador.ancora import Ancora, Fato


class ClienteFalso:
    def __init__(self, resposta):
        self.resposta, self.chamadas = resposta, []

    def completar_json(self, sistema, usuario, schema):
        self.chamadas.append((sistema, usuario, schema))
        return self.resposta


ANCORA = Ancora(fatos=[Fato(id="f1", texto="O Copom elevou a Selic para 14,25%")])
BOM = {
    "afirmacoes_sem_suporte": [], "nota_fidelidade": 5,
    "criterios_atendidos": ["a"], "criterios_nao_atendidos": [], "nota_adequacao_nivel": 5,
    "fatos_confirmados": ["f1"], "fatos_ausentes": [], "justificativa": "ok",
}


def test_prompt_traz_ancora_rubrica_e_texto():
    p = juiz.montar_prompt("Texto X", "iniciante", "artigo", ANCORA, ["f1"])
    assert "[f1]" in p and "analogia" in p and "Texto X" in p and "FATOS INDETERMINADOS" in p


def test_julgar_valida_e_aprova():
    c = ClienteFalso(BOM)
    v = juiz.julgar(c, "Texto", "iniciante", "artigo", ANCORA, ["f1"])
    assert v.aprovado and c.chamadas[0][2]["additionalProperties"] is False


def test_afirmacao_sem_suporte_reprova():
    v = juiz.julgar(ClienteFalso({**BOM, "afirmacoes_sem_suporte": ["A Selic vai a 20%"]}), "t", "iniciante", "artigo", ANCORA)
    assert not v.aprovado


def test_nota_fora_da_faixa_e_rejeitada():
    with pytest.raises(ValidationError):
        juiz.julgar(ClienteFalso({**BOM, "nota_fidelidade": 9}), "t", "iniciante", "artigo", ANCORA)


def test_schema_sem_referencias_nem_limites():
    s = str(juiz.Veredito.model_json_schema())
    assert "$ref" not in s and "$defs" not in s and "minimum" not in s


def test_cliente_groq_exige_chave(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(juiz, "ler_env", lambda nome: None)   # ignora um .env real da máquina
    with pytest.raises(RuntimeError):
        juiz.ClienteGroq()


def test_ler_env_do_arquivo(monkeypatch, tmp_path):
    monkeypatch.delenv("CHAVE_TESTE", raising=False)
    arq = tmp_path / ".env"
    arq.write_text('OUTRA=1\nCHAVE_TESTE="abc123"\n', encoding="utf-8")
    assert juiz.ler_env("CHAVE_TESTE", arq) == "abc123"
    assert juiz.ler_env("AUSENTE", arq) is None
    monkeypatch.setenv("CHAVE_TESTE", "do_ambiente")
    assert juiz.ler_env("CHAVE_TESTE", arq) == "do_ambiente"


def test_classificador_llm_cego():
    c = ClienteFalso({"nivel": "avancado", "justificativa": "jargão pleno"})
    assert classificador.classificar_por_llm(c, "Texto qualquer") == "avancado"
    assert "NÍVEL ALVO" not in c.chamadas[0][1]   # o texto vai sem o nível-alvo


def test_matriz_e_acuracia():
    reais = ["iniciante", "iniciante", "avancado", "intermediario"]
    previstos = ["iniciante", "intermediario", "avancado", "intermediario"]
    m = classificador.matriz_confusao(reais, previstos)
    assert m["iniciante"]["intermediario"] == 1 and m["avancado"]["avancado"] == 1
    assert classificador.acuracia(m) == 0.75
    assert "iniciante" in classificador.formatar(m)
    with pytest.raises(ValueError):
        classificador.matriz_confusao(["iniciante"], [])


def test_classificador_por_regras():
    from avaliador import glossario
    idx = glossario.Indice(glossario.carregar())
    facil = "Os preços sobem. O dinheiro vale menos. A gente compra menos coisas."
    medio = "A Selic subiu e o IPCA também. Os dividendos podem cair com isso."
    dificil = "O balanço de riscos e a desancoragem das expectativas pesam no horizonte relevante."
    assert classificador.classificar_por_regras(facil, idx) == "iniciante"
    assert classificador.classificar_por_regras(medio, idx) == "intermediario"
    assert classificador.classificar_por_regras(dificil, idx) == "avancado"


def test_prompt_do_juiz_aceita_consequencia_geral_mas_nao_fato_novo():
    assert "consequência econômica geral" in juiz.SISTEMA_JUIZ
    assert "número, data, nome, decisão" in juiz.SISTEMA_JUIZ


def test_retry_espera_e_repete_em_429(monkeypatch):
    import httpx
    respostas = [httpx.Response(429, headers={"retry-after": "3"}, request=httpx.Request("POST", "https://x")),
                 httpx.Response(503, request=httpx.Request("POST", "https://x")),
                 httpx.Response(200, json={"ok": 1}, request=httpx.Request("POST", "https://x"))]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: respostas.pop(0))
    esperas = []
    r = juiz.post_com_retry("https://x", {}, {}, dormir=esperas.append)
    assert r.json() == {"ok": 1} and esperas == [3.5, 4.5]


def test_retry_desiste_depois_das_tentativas(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(429, request=httpx.Request("POST", "https://x")))
    with pytest.raises(httpx.HTTPStatusError):
        juiz.post_com_retry("https://x", {}, {}, tentativas=3, dormir=lambda s: None)


def test_erro_de_cliente_nao_repete(monkeypatch):
    import httpx
    chamadas = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamadas.append(1) or httpx.Response(401, request=httpx.Request("POST", "https://x")))
    with pytest.raises(httpx.HTTPStatusError):
        juiz.post_com_retry("https://x", {}, {}, dormir=lambda s: None)
    assert len(chamadas) == 1


def test_retry_repete_400_de_json_malformado_da_groq(monkeypatch):
    import httpx
    req = httpx.Request("POST", "https://x")
    respostas = [httpx.Response(400, text='{"error":{"code":"json_validate_failed"}}', request=req),
                 httpx.Response(200, json={"ok": 1}, request=req)]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: respostas.pop(0))
    assert juiz.post_com_retry("https://x", {}, {}, dormir=lambda s: None).json() == {"ok": 1}


def test_400_comum_nao_e_repetido(monkeypatch):
    import httpx
    chamadas = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamadas.append(1) or httpx.Response(
        400, text="schema invalido", request=httpx.Request("POST", "https://x")))
    with pytest.raises(httpx.HTTPStatusError):
        juiz.post_com_retry("https://x", {}, {}, dormir=lambda s: None)
    assert len(chamadas) == 1


def test_juiz_pode_usar_outro_modelo_da_groq(monkeypatch):
    from avaliador.juiz import MODELO_PADRAO, clientes_groq
    valores = {"GROQ_API_KEY": "x"}
    monkeypatch.setattr("avaliador.juiz.ler_env", lambda nome, *a, **k: valores.get(nome))   # ignora o .env real
    extrator, juiz = clientes_groq()
    assert extrator.modelo == juiz.modelo == MODELO_PADRAO and extrator is juiz
    valores["JUIZ_MODELO"] = "openai/gpt-oss-20b"
    extrator, juiz = clientes_groq()
    assert extrator.modelo == MODELO_PADRAO and juiz.modelo == "openai/gpt-oss-20b"


def test_json_malformado_repete_poucas_vezes_e_sem_esperar_minutos(monkeypatch):
    import httpx
    req = httpx.Request("POST", "https://x")
    chamadas, esperas = [], []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamadas.append(1) or httpx.Response(
        400, text='{"error":{"code":"json_validate_failed"}}', request=req))
    with pytest.raises(httpx.HTTPStatusError):
        juiz.post_com_retry("https://x", {}, {}, dormir=esperas.append)
    assert len(chamadas) == 3            # a original e 2 repeticoes
    assert sum(esperas) <= 2.0           # espera curta, não os minutos do limite de uso
