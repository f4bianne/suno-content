from avaliador.ancora import Ancora, Fato, conferir_numeros, cobertura, normalizar_numero, numeros_em

MARCADORES = ["quase", "cerca de", "aproximadamente"]


def ancora():
    return Ancora(fatos=[
        Fato(id="f1", texto="O Copom elevou a Selic para 14,25% ao ano", numeros=["14,25"], entidades=["Copom", "Selic"]),
        Fato(id="f2", texto="A inflação em 12 meses foi de 5,06%", numeros=["5,06"], entidades=["IPCA"]),
        Fato(id="f3", texto="O comitê vê incerteza elevada no cenário"),
    ])


def test_normaliza_formatos_brasileiros():
    assert normalizar_numero("10,75") == 10.75
    assert normalizar_numero("1.234,5") == 1234.5
    assert normalizar_numero("1.234") == 1234
    assert normalizar_numero("4.26") == 4.26


def test_extrai_numeros_do_texto():
    assert numeros_em("Subiu 1,00 p.p. para 14,25% em 2025.") == [1.0, 14.25, 2025.0]


def test_numero_inventado_reprova():
    r = conferir_numeros("A Selic foi para 13,75%.", ancora(), False, 0.05, MARCADORES)
    assert r.invalidos == ["13,75"]


def test_numero_da_ancora_passa():
    r = conferir_numeros("A Selic foi para 14,25%.", ancora(), False, 0.05, MARCADORES)
    assert r.invalidos == []


def test_arredondamento_declarado_so_onde_permitido():
    texto = "A Selic está quase em 14,3%."
    assert conferir_numeros(texto, ancora(), True, 0.05, MARCADORES).arredondados == ["14,3"]
    assert conferir_numeros(texto, ancora(), False, 0.05, MARCADORES).invalidos == ["14,3"]


def test_arredondamento_sem_marcador_reprova():
    r = conferir_numeros("A Selic está em 14,3%.", ancora(), True, 0.05, MARCADORES)
    assert r.invalidos == ["14,3"]


def test_cobertura_completa_e_parcial():
    cheio = cobertura("O Copom subiu a Selic a 14,25%. O IPCA em 12 meses foi 5,06%.", ancora())
    assert cheio.fracao == 1.0 and cheio.indeterminados == ["f3"]
    parcial = cobertura("O Copom subiu a Selic a 14,25%.", ancora())
    assert parcial.fracao == 0.5 and parcial.ausentes == ["f2"]


def test_fato_sem_numero_nem_entidade_vai_para_o_juiz():
    c = cobertura("Nada relevante.", Ancora(fatos=[Fato(id="x", texto="Algo")]))
    assert c.indeterminados == ["x"] and c.fracao == 1.0
