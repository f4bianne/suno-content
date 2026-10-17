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


def test_fato_com_numero_nao_exige_a_entidade():
    texto = "A inflação em 12 meses foi de 5,06%."   # diz "inflação", não "IPCA"
    assert cobertura(texto, ancora()).presentes == ["f2"]


def test_fato_sem_numero_com_as_entidades_conta_e_sem_elas_vai_para_o_juiz():
    a = Ancora(fatos=[Fato(id="x", texto="Fato", entidades=["Copom", "Selic"])])
    assert cobertura("O Copom manteve a Selic.", a).presentes == ["x"]
    c = cobertura("O Copom decidiu.", a)          # pode ter sido dito com outras palavras ("países ricos")
    assert c.indeterminados == ["x"] and c.ausentes == []


def test_fato_com_varios_numeros_conta_com_a_maioria_quando_configurado():
    a = Ancora(fatos=[Fato(id="f", texto="IPCA livres 5,2, 4,1 e 3,2", numeros=["5,2", "4,1", "3,2"])])
    texto = "A projeção é de 5,2% e depois 4,1%."
    assert cobertura(texto, a).ausentes == ["f"]                 # padrão: todos os números
    assert cobertura(texto, a, 0.5).presentes == ["f"]
    assert cobertura("Só 5,2%.", a, 0.5).ausentes == ["f"]       # 1 de 3 não é a maioria
    assert cobertura("Nada.", a, 0.0).ausentes == ["f"]          # pelo menos um número sempre
