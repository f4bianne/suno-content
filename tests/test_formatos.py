from avaliador.avaliar import carregar_config
from avaliador.formatos import Artigo, Carrossel, Cena, Roteiro, formato_de, texto_corrido, unidades_flesch, verificar

CFG = carregar_config()["formatos"]


def test_artigo_fora_da_faixa_de_palavras():
    a = Artigo(titulo="Título", corpo="Texto curto.", conclusao="Fim.")
    assert any("palavras" in f for f in verificar(a, CFG))


def test_artigo_sem_titulo_ou_conclusao():
    corpo = "palavra " * 500
    falhas = verificar(Artigo(titulo=" ", corpo=corpo, conclusao=""), CFG)
    assert "artigo sem título" in falhas and "artigo sem conclusão" in falhas


def test_artigo_valido():
    assert verificar(Artigo(titulo="A Selic sobe", corpo="palavra " * 500, conclusao="Em resumo."), CFG) == []


def test_carrossel_limites():
    c = Carrossel(slides=["x" * 300, "ok"])
    falhas = verificar(c, CFG)
    assert any("slides" in f for f in falhas) and any("caracteres" in f for f in falhas)


def test_carrossel_valido_e_flesch_por_slide():
    c = Carrossel(slides=[f"Slide número {i} curto" for i in range(6)])
    assert verificar(c, CFG) == []
    assert unidades_flesch(c) == c.slides[1:-1]   # gancho e conclusão ficam de fora


def test_video_acima_de_60s():
    r = Roteiro(cenas=[Cena(inicio_s=0, fim_s=70, fala="Oi.", visual="gráfico", texto_tela="Selic em alta")])
    assert any("máximo 60s" in f for f in verificar(r, CFG))


def test_video_com_fala_longa_demais():
    fala = "palavra " * 200   # 200 palavras / 2,5 por segundo = 80 s
    r = Roteiro(cenas=[Cena(inicio_s=0, fim_s=50, fala=fala, visual="gráfico", texto_tela="Selic em alta")])
    assert any("leva cerca de" in f for f in verificar(r, CFG))


def test_video_sem_gancho_visual():
    r = Roteiro(cenas=[Cena(inicio_s=0, fim_s=20, fala="Olá, pessoal.", visual="")])
    assert any("gancho visual" in f for f in verificar(r, CFG))


def test_video_valido():
    r = Roteiro(cenas=[Cena(inicio_s=0, fim_s=30, fala="A Selic subiu.", visual="seta para cima", texto_tela="Selic em alta"),
                       Cena(inicio_s=30, fim_s=55, fala="Seu financiamento fica mais caro.", visual="casa", texto_tela="Selic em alta")])
    assert verificar(r, CFG) == []
    assert formato_de(r) == "video"
    assert texto_corrido(r) == "A Selic subiu.\nSeu financiamento fica mais caro."


def _cena(**kw):
    base = dict(inicio_s=0, fim_s=30, fala="A Selic subiu para 14,25% ao ano.", visual="seta para cima", texto_tela="Selic em alta")
    return Roteiro(cenas=[Cena(**{**base, **kw})])


def test_texto_na_tela_obrigatorio_curto_sem_emoji_e_sem_numero_novo():
    assert verificar(_cena(), CFG) == []
    assert any("sem texto na tela" in f for f in verificar(_cena(texto_tela=""), CFG))
    assert any("palavras (máximo 8)" in f for f in verificar(_cena(texto_tela="uma frase longa demais para caber numa legenda de vídeo curto"), CFG))
    assert any("emoji" in f for f in verificar(_cena(texto_tela="Selic em alta 📈"), CFG))
    assert any("número 14,50" in f for f in verificar(_cena(texto_tela="Selic a 14,50%"), CFG))
    assert verificar(_cena(texto_tela="Selic a 14,25%"), CFG) == []     # número que a fala diz é permitido
