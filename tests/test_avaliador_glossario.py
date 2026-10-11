import pytest

from avaliador import glossario


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


def nomes(indice, texto):
    return [o.termo.termo for o in indice.encontrar(texto)]


def test_acha_termo_e_variante(indice):
    assert "Selic" in nomes(indice, "A taxa básica de juros subiu.")
    assert "IPCA" in nomes(indice, "O IPCA fechou o mês em alta.")


def test_sigla_so_casa_em_maiusculas(indice):
    assert "CDI" in nomes(indice, "Rende 100% do CDI.")
    assert "CDI" not in nomes(indice, "o cdi não existe assim")


def test_forma_mais_longa_vence(indice):
    achados = nomes(indice, "A curva de juros futuros inverteu.")
    assert "curva de juros futuros" in achados
    assert "curva de juros" not in achados


def test_plural_e_aceito(indice):
    assert "dividendos" in nomes(indice, "A empresa pagou dividendos.")
    assert "covenants" in nomes(indice, "Os covenants foram cumpridos.")


def test_termo_ambiguo_e_ignorado_por_padrao(indice):
    assert "principal" not in nomes(indice, "O principal motivo foi o clima.")


def test_nao_casa_no_meio_de_palavra(indice):
    assert "TR" not in nomes(indice, "A estrutura da obra")


def test_iniciante_nao_aceita_nivel_3_nem_explicado(indice):
    texto = "O hiato do produto, ou seja, a folga da economia, está negativo."
    v = glossario.violacoes(texto, indice, 1, 2)
    assert any(x.termo == "hiato do produto" and x.motivo == "proibido" for x in v)


def test_iniciante_aceita_nivel_2_com_explicacao(indice):
    sem = glossario.violacoes("A Selic subiu hoje.", indice, 1, 2)
    com = glossario.violacoes("A Selic, que é a taxa básica de juros, subiu hoje.", indice, 1, 2)
    assert [x.termo for x in sem] == ["Selic"] and sem[0].motivo == "sem explicacao"
    assert com == []


def test_intermediario_aceita_nivel_3_so_com_explicacao(indice):
    sem = glossario.violacoes("O forward guidance mudou.", indice, 2, 3)
    com = glossario.violacoes("O forward guidance, ou seja, a sinalização dos próximos passos, mudou.", indice, 2, 3)
    assert len(sem) == 1 and sem[0].motivo == "sem explicacao"
    assert com == []


def test_avancado_aceita_tudo(indice):
    assert glossario.violacoes("O hiato do produto e os covenants.", indice, 3, 3) == []


def test_explicacao_na_frase_anterior_vale(indice):
    texto = "Pense em uma folga na economia. O hiato do produto mede essa folga."
    assert glossario.violacoes(texto, indice, 2, 3) == []


def test_densidade(indice):
    d = glossario.densidade("A Selic e o IPCA subiram. O hiato do produto fechou.", indice)
    assert d["contagem"][2] == 2 and d["contagem"][3] == 1
    assert d["nivel23_por_100_palavras"] > 0


def test_explicacao_logo_depois_perdoa_a_primeira_mencao(indice):
    texto = "O Copom decidiu elevar a Selic. A Selic é a taxa básica de juros da economia."
    assert [v.termo for v in glossario.violacoes(texto, indice, 1, 2)] == ["Copom"]   # só o Copom segue sem explicação


def test_explicacao_muito_longe_nao_perdoa(indice):
    texto = "A Selic subiu. " + "Os preços ficaram estáveis no mercado de bairro e na feira. " * 12 + "A Selic é a taxa básica de juros."
    assert any(v.termo == "Selic" for v in glossario.violacoes(texto, indice, 1, 2))


def test_chamada_antes_do_termo_conta_como_explicacao(indice):
    assert glossario.violacoes("Subiu a taxa básica de juros, chamada Selic, para 14,25%.", indice, 1, 2) == []
