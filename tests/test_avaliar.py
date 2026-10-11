import pytest

from avaliador import glossario
from avaliador.ancora import Ancora, Fato
from avaliador.avaliar import avaliar, carregar_config
from avaliador.formatos import Artigo, Carrossel

CFG = carregar_config()
# Faixas de formato afrouxadas: aqui se testa a lógica, não o tamanho.
CFG["formatos"]["artigo"]["palavras"] = [1, 5000]
CFG["formatos"]["carrossel"]["slides"] = [1, 20]


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


def ancora():
    return Ancora(fatos=[Fato(id="f1", texto="O Copom elevou a Selic para 14,25% ao ano", numeros=["14,25"], entidades=["Selic"])])


def artigo(corpo):
    return Artigo(titulo="Os juros subiram", corpo=corpo, conclusao="Esse é o resumo.")


def test_iniciante_bom_passa(indice):
    a = artigo("Os juros subiram. A Selic, que é a taxa básica de juros, foi para 14,25%. "
               "Isso deixa o crédito mais caro. As parcelas pesam mais no bolso.")
    r = avaliar(a, "iniciante", indice, ancora(), CFG)
    assert r.aprovado, r.resumo()


def test_iniciante_com_jargao_reprova(indice):
    a = artigo("O hiato do produto negativo e a ancoragem das expectativas pesaram sobre a Selic em 14,25%.")
    r = avaliar(a, "iniciante", indice, ancora(), CFG)
    assert not r.aprovado and any(f.metrica == "glossario" for f in r.falhas)


def test_numero_inventado_reprova_em_qualquer_nivel(indice):
    a = artigo("A Selic foi para 12,50% ao ano. Os juros subiram.")
    r = avaliar(a, "intermediario", indice, ancora(), CFG)
    assert any(f.metrica == "numeros" for f in r.falhas)


def test_recomendacao_reprova(indice):
    a = artigo("Os juros subiram. Compre títulos prefixados agora. A Selic foi para 14,25%.")
    r = avaliar(a, "iniciante", indice, ancora(), CFG)
    assert any(f.metrica == "recomendacao" for f in r.falhas)


def test_cobertura_baixa_reprova(indice):
    a = artigo("Os juros subiram bastante neste mês.")
    r = avaliar(a, "iniciante", indice, ancora(), CFG)
    assert any(f.metrica == "cobertura" for f in r.falhas)


def test_avancado_com_jargao_passa_em_glossario(indice):
    a = artigo("O Copom elevou a Selic a 14,25%, em linha com o balanço de riscos e a desancoragem das expectativas "
               "de inflação no horizonte relevante, mantendo política monetária restritiva.")
    r = avaliar(a, "avancado", indice, ancora(), CFG)
    assert not [f for f in r.falhas if f.metrica == "glossario"], r.resumo()


def test_carrossel_usa_slide_como_sentenca(indice):
    c = Carrossel(slides=["Juros sobem", "A Selic foi para 14,25%", "Crédito fica mais caro", "Parcelas pesam mais", "Fique atento"])
    r = avaliar(c, "iniciante", indice, ancora(), CFG)
    assert r.metricas["formato"] == "carrossel" and "flesch" in r.metricas


def test_video_usa_faixa_propria_de_legibilidade(indice):
    from avaliador.formatos import Cena, Roteiro
    cfg = carregar_config()
    assert cfg["niveis"]["avancado"]["flesch_video"][1] > cfg["niveis"]["avancado"]["flesch"][1]
    fala = ("O Copom elevou a Selic a 14,25% ao ano, decisão compatível com a convergência da inflação para o redor da meta. "
            "A inflação medida pelo IPCA alcançou 5,06% no acumulado de doze meses, mantendo o balanço de riscos assimétrico. "
            "A desancoragem das expectativas sustenta uma política monetária restritiva.")
    r = Roteiro(cenas=[Cena(inicio_s=0, fim_s=20, fala=fala, visual="gráfico")])
    res = avaliar(r, "avancado", indice, ancora(), cfg)
    assert 50 < res.metricas["flesch"] <= 60 and not [f for f in res.falhas if f.metrica == "legibilidade"]


def test_nivel_invalido(indice):
    with pytest.raises(ValueError):
        avaliar(artigo("x"), "expert", indice, None, CFG)
