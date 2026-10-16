import pytest
from pydantic import ValidationError

from avaliador import avaliar as av
from avaliador import glossario
from avaliador.formatos import Artigo, Carrossel, Roteiro
from geracao import grafo, prompts, revisor, schemas
from geracao.ramo import construir_ramo, rodar_ramo
from tests.fixtures_geracao import ANCORA, GeradorFalso, JuizFalso, bom


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


@pytest.fixture()
def cfg():
    c = av.carregar_config()
    c["formatos"]["artigo"]["palavras"] = [20, 900]   # os textos de exemplo são curtos
    return c


# ---------- schemas ----------

def test_conversao_dos_tres_formatos():
    assert isinstance(schemas.para_conteudo("artigo", bom("iniciante", "artigo")), Artigo)
    c = schemas.para_conteudo("carrossel", bom("iniciante", "carrossel"))
    assert isinstance(c, Carrossel) and c.slides[0] == bom("iniciante", "carrossel")["gancho"] and len(c.slides) == 6
    assert isinstance(schemas.para_conteudo("video", bom("iniciante", "video")), Roteiro)


def test_resposta_fora_do_schema_e_rejeitada():
    with pytest.raises(ValidationError):
        schemas.para_conteudo("artigo", {"titulo": "x"})
    with pytest.raises(ValidationError):
        schemas.para_conteudo("artigo", {**bom("iniciante", "artigo"), "extra": 1})


def test_schemas_sao_estritos_e_planos():
    from avaliador.juiz import schema_plano
    for modelo in schemas.SCHEMA_POR_FORMATO.values():
        s = schema_plano(modelo)
        assert "$ref" not in str(s) and "$defs" not in str(s) and s["additionalProperties"] is False


# ---------- prompts ----------

def test_prompt_traz_regras_do_nivel_e_do_formato(indice, cfg):
    ini = prompts.sistema("iniciante", "artigo", indice.termos, cfg)
    assert "TERMOS PROIBIDOS" in ini and "hiato do produto" in ini and "FORMATO: artigo" in ini
    avc = prompts.sistema("avancado", "video", indice.termos, cfg)
    assert "Todos os termos são permitidos" in avc and "FORMATO: roteiro" in avc
    assert "Selic" in prompts.sistema("iniciante", "carrossel", indice.termos, cfg)   # exige explicação


def test_prompt_do_usuario_lista_fatos_com_numeros():
    u = prompts.usuario(ANCORA)
    assert "[f1]" in u and "14,25" in u and "PROBLEMAS" not in u


# ---------- ramo: aprovação, correção e bloqueio ----------

def ramo(indice, cfg, gerador, juiz=None, max_t=3):
    return construir_ramo(gerador, juiz or JuizFalso(), indice, cfg, max_t, tentativas_juiz=1, espera_juiz_s=0)


def test_ramo_aprova_de_primeira(indice, cfg):
    r = rodar_ramo(ramo(indice, cfg, GeradorFalso(0)), "iniciante", "artigo", ANCORA)
    assert r.status == "aprovado" and len(r.tentativas) == 1
    t = r.tentativas[0]
    assert t.aprovado and t.veredito is not None and t.chamadas_llm == 2 and t.metricas["flesch"] > 60


def test_ramo_corrige_depois_do_feedback(indice, cfg):
    g = GeradorFalso(falhas_antes_de_acertar=1)
    r = rodar_ramo(ramo(indice, cfg, g), "iniciante", "artigo", ANCORA)
    assert r.status == "aprovado" and [t.aprovado for t in r.tentativas] == [False, True]
    # A segunda chamada recebeu o relatório de falhas e a versão anterior.
    segunda = g.prompts[1][1]
    assert "PROBLEMAS" in segunda and "VERSÃO ANTERIOR" in segunda and "[glossario]" in segunda
    # As regras reprovaram antes de gastar uma chamada ao juiz.
    assert r.tentativas[0].veredito is None and r.tentativas[0].chamadas_llm == 1


def test_ramo_e_bloqueado_depois_do_maximo(indice, cfg):
    r = rodar_ramo(ramo(indice, cfg, GeradorFalso(99), max_t=3), "iniciante", "artigo", ANCORA)
    assert r.status == "bloqueado" and len(r.tentativas) == 3 and not any(t.aprovado for t in r.tentativas)
    assert r.conteudo is not None   # guarda a última versão para inspeção


def test_numero_inventado_vira_feedback_no_avancado(indice, cfg):
    g = GeradorFalso(1)
    r = rodar_ramo(ramo(indice, cfg, g), "avancado", "artigo", ANCORA)
    assert r.status == "aprovado"
    assert any("[numeros]" in f for f in r.tentativas[0].falhas)


def test_juiz_reprova_e_o_feedback_chega_ao_gerador(indice, cfg):
    g, j = GeradorFalso(0), JuizFalso(rejeitar_primeiras=1)
    r = rodar_ramo(ramo(indice, cfg, g, j), "intermediario", "artigo", ANCORA)
    assert r.status == "aprovado" and len(r.tentativas) == 2
    assert any("[juiz] afirmação sem suporte" in f for f in r.tentativas[0].falhas)
    assert "A Selic vai a 20%" in g.prompts[1][1]


def test_resposta_invalida_do_gerador_e_uma_falha_nao_um_erro(indice, cfg):
    class Quebrado:
        n = 0

        def completar_json(self, sistema, usuario, schema):
            self.n += 1
            return {"titulo": "só o título"} if self.n == 1 else bom("iniciante", "artigo")

    r = rodar_ramo(ramo(indice, cfg, Quebrado()), "iniciante", "artigo", ANCORA)
    assert r.status == "aprovado" and "[formato]" in r.tentativas[0].falhas[0] and r.tentativas[0].conteudo is None


def test_erro_do_juiz_nao_aprova_por_engano(indice, cfg):
    class JuizQuebrado:
        def completar_json(self, *a):
            raise RuntimeError("fora do ar")

    r = rodar_ramo(ramo(indice, cfg, GeradorFalso(0), JuizQuebrado(), max_t=2), "iniciante", "artigo", ANCORA)
    assert r.status == "bloqueado" and "[juiz]" in r.tentativas[0].falhas[0]


def test_feedback_de_cobertura_lista_os_fatos_que_faltaram(indice, cfg):
    class SoUmFato:
        n = 0

        def completar_json(self, sistema, usuario, schema):
            self.n += 1
            if self.n == 1:
                return {"titulo": "Juros", "corpo": "A Selic, que é a taxa básica de juros, subiu para 14,25% ao ano.", "conclusao": "Fim."}
            return bom("iniciante", "artigo")

    r = rodar_ramo(ramo(indice, cfg, SoUmFato()), "iniciante", "artigo", ANCORA)
    assert any("[cobertura]" in f and "[f2]" in f for f in r.tentativas[0].falhas)


# ---------- grafo completo ----------

def clientes(gerador=None, juiz=None):
    return grafo.Clientes(extrator=None, gerador=gerador or GeradorFalso(0), juiz=juiz or JuizFalso())


def doc():
    from ingestao.documento import Documento, Proveniencia
    return Documento(texto="texto", proveniencia=Proveniencia(tipo="termo", origem="Copom", url="https://x", sha256_bruto="0" * 64))


def test_grafo_gera_os_nove_ramos(indice, cfg):
    p = grafo.processar(doc(), clientes(), indice, cfg, ancora=ANCORA)
    assert len(p.ramos) == 9
    assert {(r.nivel, r.formato) for r in p.ramos} == {(n, f) for n in av.NIVEIS for f in schemas.FORMATOS}
    assert all(r.status == "aprovado" for r in p.ramos)
    assert p.matriz()["avancado"]["video"] == "aprovado" and p.origem == "Copom"


def test_ramos_com_defeito_sao_corrigidos_cada_um_por_si(indice, cfg):
    g = GeradorFalso(falhas_antes_de_acertar=1)
    p = grafo.processar(doc(), clientes(g), indice, cfg, ancora=ANCORA)
    assert all(r.status == "aprovado" and len(r.tentativas) == 2 for r in p.ramos)


def test_um_ramo_bloqueado_nao_derruba_os_outros(indice, cfg):
    class SoIniciantePrejudicado(GeradorFalso):
        def completar_json(self, sistema, usuario, schema):
            n, f = __import__("tests.fixtures_geracao", fromlist=["x"]).nivel_e_formato(sistema)
            if (n, f) == ("iniciante", "video"):
                return {"cenas": []}   # nunca passa
            return super().completar_json(sistema, usuario, schema)

    p = grafo.processar(doc(), clientes(SoIniciantePrejudicado(0)), indice, cfg, ancora=ANCORA, max_tentativas=2)
    status = {(r.nivel, r.formato): r.status for r in p.ramos}
    assert status[("iniciante", "video")] == "bloqueado" and list(status.values()).count("aprovado") == 8


def test_niveis_e_formatos_podem_ser_restringidos(indice, cfg):
    p = grafo.processar(doc(), clientes(), indice, cfg, ancora=ANCORA, niveis=("iniciante",), formatos=("artigo", "video"))
    assert [(r.nivel, r.formato) for r in p.ramos] == [("iniciante", "artigo"), ("iniciante", "video")]


def test_nivel_prioritario_vai_primeiro():
    pedidos = [(n, f) for n in av.NIVEIS for f in schemas.FORMATOS]
    assert grafo.ordenar(pedidos, "avancado")[:3] == [("avancado", f) for f in schemas.FORMATOS]
    assert grafo.ordenar(pedidos, None) == pedidos


def test_ancora_vazia_para_o_grafo_com_mensagem_clara(indice, cfg):
    from avaliador.ancora import Ancora
    with pytest.raises(ValueError, match="âncora ficou vazia"):
        grafo.processar(doc(), clientes(), indice, cfg, ancora=Ancora(fatos=[]))


def test_extrator_roda_quando_nao_ha_ancora(indice, cfg):
    class ExtratorFalso:
        def completar_json(self, sistema, usuario, schema):
            return {"fatos": [{"texto": "O Copom elevou a Selic para 14,25% ao ano", "numeros": ["14,25%"], "entidades": ["Selic"],
                               "trecho_origem": "O Copom elevou a Selic para 14,25% ao ano em março"}]}

    from ingestao.documento import Documento, Proveniencia
    d = Documento(texto="O Copom elevou a Selic para 14,25% ao ano em março, segundo a ata.",
                  proveniencia=Proveniencia(tipo="termo", origem="Copom", sha256_bruto="0" * 64))
    c = grafo.Clientes(extrator=ExtratorFalso(), gerador=GeradorFalso(0), juiz=JuizFalso())
    p = grafo.processar(d, c, indice, cfg, niveis=("iniciante",), formatos=("artigo",))
    assert [f.numeros for f in p.ancora.fatos] == [["14,25"]]


def test_juiz_indisponivel_nao_gasta_tentativa(indice, cfg):
    class JuizInstavel(JuizFalso):
        def completar_json(self, sistema, usuario, schema):
            if self.n < 2:
                self.n += 1
                raise RuntimeError("limite de uso")
            return super().completar_json(sistema, usuario, schema)

    r = rodar_ramo(ramo(indice, cfg, GeradorFalso(0), JuizInstavel(), max_t=1), "iniciante", "artigo", ANCORA)
    # Com max_t=1, sem a regra o ramo seria bloqueado na primeira queda do juiz.
    assert r.status == "aprovado" and len(r.tentativas) == 3


def test_juiz_sempre_fora_do_ar_acaba_bloqueando(indice, cfg):
    class JuizMorto:
        def completar_json(self, *a):
            raise RuntimeError("fora do ar")

    r = rodar_ramo(ramo(indice, cfg, GeradorFalso(0), JuizMorto(), max_t=2), "iniciante", "artigo", ANCORA)
    assert r.status == "bloqueado" and len(r.tentativas) == 4   # 2 perdoadas + 2 contadas


def test_feedback_de_legibilidade_traz_alvo_numerico():
    from avaliador.avaliar import Falha
    from geracao.ramo import _dica
    msg = _dica(Falha("legibilidade", "Flesch 39.0 fora da faixa 40 a 60"), ANCORA, {"flesch": 39.0})
    assert "cerca de 50" in msg and "mais curtas" in msg
    msg2 = _dica(Falha("legibilidade", "Flesch 63.0 fora da faixa 40 a 60"), ANCORA, {"flesch": 63.0})
    assert "mais longas" in msg2


def test_feedback_de_glossario_traz_a_explicacao_pronta():
    from avaliador.avaliar import Falha
    from geracao.ramo import _dica
    indice = glossario.Indice([glossario.Termo("Selic", 2, "juros", ("Selic",), False, "a taxa básica de juros da economia")])
    msg = _dica(Falha("glossario", "termo de nível 2 sem explicacao: 'Selic' em \"...a Selic subiu...\""), ANCORA, {}, indice)
    assert "Selic, que é a taxa básica de juros da economia" in msg
    sem = _dica(Falha("glossario", "termo de nível 2 sem explicacao: 'Selic' em \"...\""), ANCORA, {})
    assert "que é a taxa básica" not in sem   # sem o índice, só a orientação genérica


def test_feedback_de_numeros_lista_os_permitidos():
    from avaliador.avaliar import Falha
    from geracao.ramo import _dica
    msg = _dica(Falha("numeros", "número '231' não existe na âncora"), ANCORA, {})
    permitidos = sorted({n for f in ANCORA.fatos for n in f.numeros})
    assert permitidos and all(n in msg for n in permitidos) and "Não calcule" in msg


def test_relatorio_pede_para_manter_o_que_estava_certo():
    from avaliador.formatos import Artigo
    r = prompts.relatorio_de_falhas(["[cobertura] x"], Artigo(titulo="t", corpo="c", conclusao="k"))
    assert "copie literalmente tudo que já estava certo" in r


def test_prompt_do_video_pede_texto_cheio_e_uma_cena_por_fato():
    cfg = {"formatos": {"video": {"duracao_maxima_s": 60, "palavras_por_segundo": 2.5}}}
    txt = prompts.instrucao_formato("video", cfg)
    assert "entre 120 e 140 palavras" in txt
    assert "CADA fato" in txt
    assert "priorize" not in txt          # mandar priorizar derrubava a cobertura dos fatos


def test_artigo_curto_pede_para_aumentar_e_nao_para_cortar():
    from avaliador.avaliar import Falha
    from geracao.ramo import _dica
    curto = _dica(Falha("formato", "artigo com 172 palavras (esperado de 250 a 900)"), ANCORA, {})
    assert "faltam pelo menos 78" in curto and "cerca de 370" in curto and "corte" not in curto
    longo = _dica(Falha("formato", "artigo com 950 palavras (esperado de 250 a 900)"), ANCORA, {})
    assert "corte" in longo


def test_prompt_do_artigo_mira_acima_do_minimo():
    cfg = {"formatos": {"artigo": {"palavras": [250, 900]}}}
    txt = prompts.instrucao_formato("artigo", cfg)
    assert "entre 400 e 650 palavras" in txt and "4 a 5 parágrafos" in txt


def test_tempo_do_roteiro_sai_do_tamanho_da_fala():
    cenas = [{"fala": " ".join(["palavra"] * 25), "visual": "a"}, {"fala": " ".join(["palavra"] * 50), "visual": "b"},
             {"fala": "Fim.", "visual": "c"}]
    r = schemas.para_conteudo("video", {"cenas": cenas})
    marcas = [(c.inicio_s, c.fim_s) for c in r.cenas]
    assert marcas == [(0, 10), (10, 30), (30, 31)]          # 25 e 50 palavras a 2,5 por segundo; a última, no mínimo 1 s
    assert all(c.fim_s > c.inicio_s for c in r.cenas) and r.cenas[0].inicio_s == 0
    assert all(a.fim_s == b.inicio_s for a, b in zip(r.cenas, r.cenas[1:]))   # sem lacunas


def test_prompt_do_video_pede_falas_mais_longas_e_sem_texto_na_tela():
    cfg = {"formatos": {"video": {"duracao_maxima_s": 60, "palavras_por_segundo": 2.5}}}
    txt = prompts.instrucao_formato("video", cfg)
    assert "entre 120 e 140 palavras" in txt and "de 15 a 30 palavras" in txt
    assert "texto_tela" not in txt and "legenda" not in txt


def test_iniciante_recebe_a_explicacao_pronta_dos_termos_do_documento():
    termos = [glossario.Termo("Selic", 2, "juros", ("Selic",), False, "a taxa basica de juros da economia"),
              glossario.Termo("hiato do produto", 3, "macro", ("hiato do produto",), False, "folga da economia"),
              glossario.Termo("IPCA", 2, "inflacao", ("IPCA",), False, "o indice oficial de inflacao")]
    txt = prompts.sistema("iniciante", "artigo", termos, {"formatos": {"artigo": {"palavras": [250, 900]}}}, ANCORA)
    assert "Selic, que é a taxa basica de juros da economia" in txt
    assert "IPCA, que é o indice oficial de inflacao" in txt
    assert "hiato do produto" not in txt.split("TERMOS DESTE DOCUMENTO")[1].split("FORMATO")[0]   # não está nos fatos
    avancado = prompts.sistema("avancado", "artigo", termos, {"formatos": {"artigo": {"palavras": [250, 900]}}}, ANCORA)
    assert "TERMOS DESTE DOCUMENTO" not in avancado


def test_termo_proibido_no_iniciante_lista_as_variantes_que_os_fatos_usam():
    from avaliador.ancora import Ancora, Fato
    termos = [glossario.Termo("inflação subjacente", 3, "indices", ("inflação subjacente", "núcleos", "núcleo da inflação"), False,
                              "medida que tira da inflação os itens mais voláteis")]
    ancora = Ancora(fatos=[Fato(id="f1", texto="A média dos núcleos ficou em 3,9%", numeros=["3,9"], entidades=[],
                                trecho_origem="a média dos núcleos ficou em 3,9%")])
    cfg_a = {"formatos": {"artigo": {"palavras": [250, 900]}}}
    ini = prompts.sistema("iniciante", "artigo", termos, cfg_a, ancora)
    assert "inflação subjacente (vale também para: núcleos, núcleo da inflação) é PROIBIDO" in ini
    assert "medida que tira da inflação os itens mais voláteis" in ini
    inter = prompts.sistema("intermediario", "artigo", termos, cfg_a, ancora)
    assert "inflação subjacente (vale também para: núcleos, núcleo da inflação), que é medida que tira" in inter


def test_cobertura_no_iniciante_pede_frase_propria_e_curta_para_cada_fato():
    from avaliador.avaliar import Falha
    from geracao.ramo import _dica
    f = Falha("cobertura", "cobertura 50% abaixo de 80%; ausentes: f1")
    ini = _dica(f, ANCORA, {"fatos_ausentes": ["f1"]}, None, "iniciante")
    assert "frase só dele, com até 15 palavras" in ini
    assert "frase só dele" not in _dica(f, ANCORA, {"fatos_ausentes": ["f1"]}, None, "avancado")


def test_revisor_e_lembrado_de_que_acrescentar_fato_derruba_a_leitura():
    assert "Acrescentar fatos costuma piorar a legibilidade" in revisor.SISTEMA
