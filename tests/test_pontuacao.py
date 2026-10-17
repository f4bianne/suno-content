import pytest

from avaliador import avaliar as av
from avaliador.avaliar import Avaliacao, Falha
from avaliador.juiz import Veredito
from avaliador.pontuacao import pontuar, vale_chamar_o_juiz


@pytest.fixture()
def cfg():
    return av.carregar_config()


def res(falhas=(), flesch=50.0, formato="artigo", **metricas):
    m = {"nivel": "intermediario", "formato": formato, "flesch": flesch, "cobertura": 1.0, "fatos_presentes": ["f1", "f2"],
         "fatos_ausentes": [], "densidade": {"nivel23_por_100_palavras": 3.0}, **metricas}
    falhas = list(falhas)
    return Avaliacao(not falhas, falhas, m, [])


def veredito(**kw):
    base = dict(afirmacoes_sem_suporte=[], nota_fidelidade=5, criterios_atendidos=[], criterios_nao_atendidos=[],
                nota_adequacao_nivel=5, fatos_confirmados=[], fatos_ausentes=[], justificativa="")
    return Veredito(**{**base, **kw})


def test_texto_sem_problemas_tem_nota_maxima_e_aprova(cfg):
    n = pontuar(res(), "intermediario", cfg, veredito())
    assert n.total == 1.0 and n.aprovado and n.resumo().startswith("NOTA 1.00")


def test_um_problema_leve_nao_reprova_mais(cfg):
    """Antes, qualquer falha reprovava: um termo sem explicação derrubava um texto bom."""
    r = res([Falha("glossario", "termo de nível 3 sem explicacao: 'hiato do produto' em \"...\"")])
    n = pontuar(r, "intermediario", cfg, veredito())
    assert n.por_metrica["glossario"] == 0.75 and n.aprovado


def test_bloqueio_reprova_com_qualquer_nota(cfg):
    for metrica in ("numeros", "recomendacao", "duracao"):
        n = pontuar(res([Falha(metrica, "x")]), "intermediario", cfg, veredito())
        assert n.total == 1.0 and not n.aprovado and n.bloqueios == [metrica]
    baixa = pontuar(res(), "intermediario", cfg, veredito(nota_fidelidade=3))
    assert baixa.bloqueios == ["fidelidade"] and not baixa.aprovado


def test_a_media_nao_esconde_uma_metrica_muito_ruim(cfg):
    """Texto avançado entregue como intermediário: Flesch 11 pontos abaixo da faixa e o resto perfeito."""
    n = pontuar(res([Falha("legibilidade", "Flesch 29 fora da faixa 40 a 60")], flesch=29.0), "intermediario", cfg, veredito())
    assert n.total >= n.limiar and n.abaixo_do_piso == ["legibilidade"] and not n.aprovado
    assert "Abaixo do mínimo" in n.resumo()


def test_legibilidade_cai_aos_poucos_fora_da_faixa(cfg):
    dentro = pontuar(res(flesch=50), "intermediario", cfg).por_metrica["legibilidade"]
    perto = pontuar(res(flesch=37), "intermediario", cfg).por_metrica["legibilidade"]
    longe = pontuar(res(flesch=10), "intermediario", cfg).por_metrica["legibilidade"]
    assert dentro == 1.0 and 0.6 < perto < 1.0 and longe == 0.0


def test_cobertura_soma_os_fatos_que_o_juiz_confirmou(cfg):
    r = res(fatos_presentes=["f1"], fatos_ausentes=[])
    r.indeterminados = ["f2", "f3"]
    assert pontuar(r, "intermediario", cfg, veredito(fatos_confirmados=["f2", "f3"])).por_metrica["cobertura"] == 1.0
    parcial = pontuar(r, "intermediario", cfg, veredito(fatos_confirmados=["f2"])).por_metrica["cobertura"]
    assert parcial == pytest.approx((2 / 3) / 0.8, abs=1e-3)


def test_rubrica_e_afirmacoes_do_juiz_entram_na_nota(cfg):
    ini = res(flesch=75.0)
    um = pontuar(ini, "iniciante", cfg, veredito(criterios_nao_atendidos=["analogia"]))
    assert um.por_metrica["rubrica"] == 0.5 and um.aprovado                      # 1 de 2 itens: ressalva
    dois = pontuar(ini, "iniciante", cfg, veredito(criterios_nao_atendidos=["a", "b"]))
    assert dois.abaixo_do_piso == ["rubrica"] and not dois.aprovado
    nivel_errado = pontuar(ini, "iniciante", cfg, veredito(nota_adequacao_nivel=2))      # itens ok, mas nível errado
    assert nivel_errado.por_metrica["rubrica"] == 0.25 and not nivel_errado.aprovado
    assert pontuar(ini, "iniciante", cfg, veredito(nota_adequacao_nivel=4)).aprovado
    sem_suporte = pontuar(ini, "iniciante", cfg, veredito(afirmacoes_sem_suporte=["é como caminhar na neblina"]))
    assert sem_suporte.por_metrica["fidelidade"] == 0.75 and sem_suporte.aprovado


def test_sem_juiz_nao_aprova_e_o_juiz_so_e_chamado_quando_pode_mudar_o_resultado(cfg):
    teto = pontuar(res(), "intermediario", cfg, juiz="nao_chamado")
    assert not teto.aprovado and vale_chamar_o_juiz(teto)
    assert not vale_chamar_o_juiz(pontuar(res([Falha("numeros", "x")]), "intermediario", cfg))
    ruim = res([Falha("glossario", "a"), Falha("glossario", "b"), Falha("formato", "c"), Falha("formato", "d")], flesch=30)
    assert not vale_chamar_o_juiz(pontuar(ruim, "intermediario", cfg))


def test_duracao_do_video_tem_etiqueta_propria_e_bloqueia(cfg):
    from avaliador import glossario
    from avaliador.formatos import Cena, Roteiro
    r = Roteiro(cenas=[Cena(inicio_s=0, fim_s=70, fala="palavra " * 180, visual="v")])
    avaliado = av.avaliar(r, "intermediario", glossario.Indice([]), None, cfg)
    assert {f.metrica for f in avaliado.falhas} >= {"duracao"}
    assert "duracao" in pontuar(avaliado, "intermediario", cfg, veredito()).bloqueios


def test_ramo_aprova_com_ressalva_e_guarda_a_nota(cfg):
    from avaliador import glossario
    from geracao.ramo import construir_ramo, rodar_ramo
    from tests.fixtures_geracao import ANCORA, GeradorFalso, JuizFalso

    class JuizComRessalva(JuizFalso):
        def completar_json(self, sistema, usuario, schema):
            return {**super().completar_json(sistema, usuario, schema),
                    "criterios_nao_atendidos": ["O texto diz o que muda para o bolso de quem lê."]}

    cfg["formatos"]["artigo"]["palavras"] = [20, 900]
    ramo = construir_ramo(GeradorFalso(0), JuizComRessalva(), glossario.Indice(glossario.carregar()), cfg, 2,
                          tentativas_juiz=1, espera_juiz_s=0)
    r = rodar_ramo(ramo, "iniciante", "artigo", ANCORA)
    t = r.tentativas[0]
    assert r.status == "aprovado" and len(r.tentativas) == 1
    assert t.falhas and t.falhas[0].startswith("[juiz] critério do nível não atendido")      # a ressalva fica registrada
    assert t.metricas["nota"]["aprovado"] and t.metricas["nota"]["por_metrica"]["rubrica"] == 0.5


def test_reescrita_recebe_a_nota_como_feedback_numerico():
    from avaliador.formatos import Artigo
    from geracao import prompts
    txt = prompts.relatorio_de_falhas(["[cobertura] x"], Artigo(titulo="t", corpo="c", conclusao="k"), "NOTA 0.72 (mínimo 0.85).")
    assert "NOTA 0.72 (mínimo 0.85)" in txt and "ÚLTIMA tentativa" in txt
