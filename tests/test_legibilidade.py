import pytest

from avaliador.legibilidade import flesch_pt
from avaliador.texto import palavras, sentencas, silabas


def test_silabas_em_portugues():
    assert silabas("casa") == 2
    assert silabas("rentabilidade") == 6
    assert silabas("juros") == 2
    assert silabas("10,75") == 1


def test_palavras_ignoram_pontuacao_e_mantem_hifen():
    assert palavras("O Copom elevou a Selic, ok? Taxa pós-fixada.") == [
        "O", "Copom", "elevou", "a", "Selic", "ok", "Taxa", "pós-fixada"]


def test_sentencas_nao_quebram_em_decimal_nem_sigla():
    texto = "A Selic subiu para 14,25% ao ano. A alta foi de 1 p.p. no mês. Foi uma surpresa?"
    assert sentencas(texto) == [
        "A Selic subiu para 14,25% ao ano.", "A alta foi de 1 p.p. no mês.", "Foi uma surpresa?"]


def test_flesch_confere_com_a_formula():
    texto = "O gato come o rato."
    r = flesch_pt(texto)
    esperado = 248.835 - 1.015 * (5 / 1) - 84.6 * (8 / 5)   # o-ga-to-co-me-o-ra-to = 8 sílabas
    assert r.palavras == 5 and r.sentencas == 1
    assert r.flesch == pytest.approx(esperado)


def test_texto_simples_pontua_mais_que_texto_tecnico():
    simples = "Os preços sobem. O dinheiro vale menos. A gente compra menos coisas."
    tecnico = ("A convergência da inflação para a meta depende da ancoragem das expectativas "
               "e do balanço de riscos em relação ao horizonte relevante.")
    assert flesch_pt(simples).flesch > flesch_pt(tecnico).flesch + 40


def test_unidades_explicitas_para_carrossel():
    slides = ["Juros altos", "O crédito fica mais caro e o consumo desacelera"]
    r = flesch_pt("", unidades=slides)
    assert r.sentencas == 2


def test_texto_vazio():
    assert flesch_pt("") is None
