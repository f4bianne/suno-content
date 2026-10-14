import pytest
from pydantic import ValidationError

from avaliador import avaliar as av
from avaliador import glossario
from avaliador.formatos import Artigo, Carrossel, Roteiro
from geracao import grafo, prompts, schemas
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
    assert "Mantenha o que já estava certo" in r
