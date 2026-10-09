import pytest

from avaliador import recomendacao


@pytest.mark.parametrize("texto", [
    "Compre títulos do Tesouro agora.",
    "Recomendamos investir em renda fixa.",
    "Vale a pena aplicar nesse fundo.",
    "É hora de vender suas ações.",
    "Você deve investir mais.",
    "Retorno garantido de 12%.",
    "Aproveite a alta da Selic.",
])
def test_detecta_recomendacao(texto):
    assert recomendacao.achar(texto)


@pytest.mark.parametrize("texto", [
    "O Copom elevou a Selic para 15% ao ano.",
    "A venda de títulos públicos reduziu a liquidez.",
    "O resgate de cotas subiu no mês.",
    "O Banco Central compra e vende títulos no mercado aberto.",
    "A inflação deve convergir para a meta.",
    "Os investidores recomendam cautela, segundo a pesquisa.",
])
def test_nao_acusa_texto_informativo(texto):
    assert recomendacao.achar(texto) == []
