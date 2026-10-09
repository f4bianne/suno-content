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
    with pytest.raises(RuntimeError):
        juiz.ClienteGroq()


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
