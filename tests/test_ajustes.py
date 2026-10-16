import pytest

from avaliador import avaliar as av
from avaliador import glossario
from avaliador.formatos import Artigo, Carrossel, Cena, Roteiro
from geracao import ajustes, prompts
from tests.fixtures_geracao import ANCORA


@pytest.fixture()
def cfg():
    return av.carregar_config()


@pytest.fixture()
def indice():
    termos = [
        glossario.Termo("Selic", 2, "juros", ("Selic", "taxa Selic"), False, "a taxa básica de juros da economia"),
        glossario.Termo("IPCA", 2, "indices", ("IPCA",), False, "o índice oficial de inflação"),
        glossario.Termo("hiato do produto", 3, "macro", ("hiato do produto",), False, "a folga da economia"),
        glossario.Termo("juros", 1, "basico", ("juros",), False, "preço do dinheiro"),
    ]
    return glossario.Indice(termos)


def _violacoes(texto, indice, cfg, nivel):
    r = cfg["niveis"][nivel]
    return glossario.violacoes(texto, indice, r["nivel_maximo_termo_sem_explicacao"], r["nivel_maximo_termo_com_explicacao"])


def test_primeira_mencao_sem_explicacao_ganha_a_definicao_e_passa_no_avaliador(indice, cfg):
    a = Artigo(titulo="A Selic sobe", corpo="O Copom elevou a Selic. A Selic fica em 14,25%.", conclusao="O IPCA preocupa.")
    assert _violacoes(f"{a.titulo}\n{a.corpo}\n{a.conclusao}", indice, cfg, "iniciante")        # antes: reprovava
    novo, feitos = ajustes.explicar_termos(a, "iniciante", indice, cfg)
    assert feitos == ["Selic", "IPCA"]
    assert novo.titulo == "A Selic, que é a taxa básica de juros da economia, sobe"
    assert novo.corpo == "O Copom elevou a Selic. A Selic fica em 14,25%."                       # só a primeira menção, no título
    assert novo.conclusao == "O IPCA, que é o índice oficial de inflação, preocupa."
    assert not _violacoes(f"{novo.titulo}\n{novo.corpo}\n{novo.conclusao}", indice, cfg, "iniciante")


def test_termo_ja_explicado_ou_com_explicacao_logo_depois_nao_e_mexido(indice, cfg):
    a = Artigo(titulo="T", corpo="A Selic, que é a taxa básica, subiu. O IPCA vem logo, ou seja, o índice de preços; veja o IPCA.",
               conclusao="Fim.")
    novo, feitos = ajustes.explicar_termos(a, "iniciante", indice, cfg)
    assert feitos == [] and novo == a


def test_termo_proibido_no_nivel_nao_e_mexido_e_avancado_nao_recebe_nada(indice, cfg):
    a = Artigo(titulo="T", corpo="O hiato do produto fechou.", conclusao="Fim.")
    novo, feitos = ajustes.explicar_termos(a, "iniciante", indice, cfg)         # nível 3 é proibido no iniciante
    assert feitos == [] and novo == a
    assert ajustes.explicar_termos(Artigo(titulo="T", corpo="A Selic subiu.", conclusao="F"), "avancado", indice, cfg)[1] == []
    inter, feitos = ajustes.explicar_termos(a, "intermediario", indice, cfg)     # nível 3 precisa de explicação no intermediário
    assert feitos == ["hiato do produto"] and "hiato do produto, que é a folga da economia" in inter.corpo


def test_carrossel_respeita_o_limite_de_caracteres_do_slide(indice, cfg):
    limite = cfg["formatos"]["carrossel"]["caracteres_por_slide"]
    cheio = "A Selic " + "x" * (limite - 10)
    c = Carrossel(slides=["Gancho da Selic", cheio, "Fim"])
    novo, feitos = ajustes.explicar_termos(c, "iniciante", indice, cfg)
    assert novo.slides[0] == "Gancho da Selic, que é a taxa básica de juros da economia" and feitos == ["Selic"]
    assert novo.slides[1] == cheio                                              # a explicação já foi dada no gancho
    c2 = Carrossel(slides=["Gancho", cheio, "Fim"])
    novo2, feitos2 = ajustes.explicar_termos(c2, "iniciante", indice, cfg)
    assert novo2.slides[1] == cheio and feitos2 == []                           # estouraria o slide: fica como está


def test_roteiro_recalcula_o_tempo_com_a_fala_maior(indice, cfg):
    r = Roteiro(cenas=[Cena(inicio_s=0, fim_s=4, fala="A Selic subiu hoje, dizem os analistas do mercado financeiro.", visual="a"),
                       Cena(inicio_s=4, fim_s=8, fala="O crédito fica mais caro para todos.", visual="b")])
    novo, feitos = ajustes.explicar_termos(r, "iniciante", indice, cfg)
    assert feitos == ["Selic"] and "Selic, que é a taxa básica" in novo.cenas[0].fala
    assert novo.cenas[0].inicio_s == 0 and novo.cenas[0].fim_s > 4              # mais palavras, mais tempo
    assert novo.cenas[0].fim_s == novo.cenas[1].inicio_s and novo.cenas[1].fim_s > novo.cenas[1].inicio_s


def test_prompt_tem_faixa_de_leitura_e_conferencia_com_os_numeros_obrigatorios(cfg):
    txt = prompts.sistema("iniciante", "artigo", [], cfg, ANCORA)
    assert "entre 60 e 100; mire perto de 80" in txt and "frases de 8 a 14 palavras" in txt
    assert "CONFERÊNCIA ANTES DE RESPONDER" in txt and "f1 (14,25)" in txt and "f3 (sem número: cite a ideia)" in txt
    assert "entre 40 e 60; mire perto de 50" in prompts.sistema("intermediario", "artigo", [], cfg, ANCORA)
    assert "entre 0 e 50; mire perto de 25" in prompts.sistema("avancado", "artigo", [], cfg, ANCORA)
    assert "entre 60 e 100" in prompts.sistema("iniciante", "video", [], cfg, ANCORA)
    assert "CONFERÊNCIA" not in prompts.sistema("iniciante", "artigo", [], cfg, None)


def test_reescrita_e_apresentada_como_ultima_e_cirurgica():
    from avaliador.formatos import Artigo as A
    txt = prompts.relatorio_de_falhas(["[cobertura] x"], A(titulo="t", corpo="c", conclusao="k"))
    assert "ÚLTIMA tentativa" in txt and "CIRÚRGICA" in txt and "copie literalmente" in txt


def test_no_ramo_o_termo_sem_explicacao_nao_gasta_tentativa(cfg):
    from geracao.ramo import construir_ramo, rodar_ramo
    from tests.fixtures_geracao import GeradorFalso, JuizFalso, bom

    class GeradorSemExplicar(GeradorFalso):
        def completar_json(self, sistema, usuario, schema):
            r = super().completar_json(sistema, usuario, schema)
            return {**r, "corpo": "O CDB foi citado no documento. " + r["corpo"]} if "corpo" in r else r

    cfg["formatos"]["artigo"]["palavras"] = [20, 900]
    real = glossario.Indice(glossario.carregar())
    ramo = construir_ramo(GeradorSemExplicar(0), JuizFalso(), real, cfg, 2, tentativas_juiz=1, espera_juiz_s=0)
    r = rodar_ramo(ramo, "iniciante", "artigo", ANCORA)
    t = r.tentativas[0]
    assert "CDB" in t.metricas.get("explicacoes_inseridas", [])
    assert not any("sem explicacao" in f and "CDB" in f for f in t.falhas)
    assert "CDB, que é" in t.conteudo["corpo"]
    assert bom("iniciante", "artigo")["corpo"] in t.conteudo["corpo"]           # o resto do texto continua o mesmo


def test_iniciante_exige_analogia_para_cada_conceito_na_primeira_tentativa(cfg):
    txt = prompts.sistema("iniciante", "artigo", [], cfg, ANCORA)
    assert "TODO conceito financeiro" in txt and "é como" in txt
    assert "uma analogia do dia a dia para cada termo (reprova se um só conceito ficar sem)" in txt
    assert "analogia" not in prompts.conferencia_final(ANCORA, "intermediario")


def test_termo_do_documento_vem_com_pedido_de_analogia_so_no_iniciante(cfg):
    from avaliador.ancora import Ancora, Fato
    termos = [glossario.Termo("Selic", 2, "juros", ("Selic",), False, "a taxa básica de juros da economia")]
    ancora = Ancora(fatos=[Fato(id="f1", texto="A Selic subiu a 14,25%", numeros=["14,25"], entidades=[], trecho_origem="A Selic subiu")])
    ini = prompts.sistema("iniciante", "artigo", termos, cfg, ancora)
    assert "Selic, que é a taxa básica de juros da economia; em seguida, uma analogia do dia a dia" in ini
    termos3 = [glossario.Termo("hiato do produto", 3, "macro", ("hiato do produto",), False, "a folga da economia")]
    anc3 = Ancora(fatos=[Fato(id="f1", texto="O hiato do produto fechou", numeros=[], entidades=[], trecho_origem="hiato do produto")])
    inter = prompts.sistema("intermediario", "artigo", termos3, cfg, anc3)
    assert "hiato do produto, que é a folga da economia" in inter and "analogia do dia a dia no molde" not in inter


def test_reprovacao_por_analogia_vem_com_orientacao_para_cada_termo():
    from avaliador.juiz import Veredito
    from geracao.ramo import _falhas_do_juiz
    v = Veredito(afirmacoes_sem_suporte=[], nota_fidelidade=5, criterios_atendidos=[],
                 criterios_nao_atendidos=["Cada conceito financeiro é traduzido em analogia do dia a dia (zero jargão desacompanhado de analogia)."],
                 nota_adequacao_nivel=3, fatos_confirmados=[], fatos_ausentes=[], justificativa="x")
    msg = _falhas_do_juiz(v)[0]
    assert "CADA termo técnico" in msg and "X é como" in msg and "Basta um termo sem analogia" in msg
    outro = Veredito(afirmacoes_sem_suporte=[], nota_fidelidade=5, criterios_atendidos=[],
                     criterios_nao_atendidos=["O texto diz o que muda para o bolso de quem lê."], nota_adequacao_nivel=3,
                     fatos_confirmados=[], fatos_ausentes=[], justificativa="x")
    assert "analogia" not in _falhas_do_juiz(outro)[0]


def test_revisor_sabe_listar_os_termos_sem_analogia():
    from geracao import revisor
    assert "TODOS os termos técnicos do texto" in revisor.SISTEMA and "X é como" in revisor.SISTEMA


# ---------- itens que mais reprovam depois das primeiras rodadas ----------

def test_termo_seguido_de_que_e_sem_virgula_conta_como_explicado(indice, cfg):
    idx = glossario.Indice(glossario.carregar())
    for texto in ("Setores sensíveis ao ciclo econômico que é a oscilação das vendas e da renda.",
                  "Setores sensíveis ao ciclo econômico, que é a oscilação das vendas e da renda."):
        assert not glossario.violacoes(texto, idx, 1, 2), texto
    assert glossario.violacoes("Setores sensíveis ao ciclo econômico pesam nas vendas.", idx, 1, 2)   # sem explicação continua reprovando


def test_slide_acima_do_limite_diz_quantos_caracteres_cortar():
    from avaliador.avaliar import Falha
    from geracao.ramo import _dica
    msg = _dica(Falha("formato", "slide 3 com 228 caracteres (máximo 220)"), ANCORA, {})
    assert "O slide 3 tem 228 caracteres e o máximo é 220: corte pelo menos 28" in msg and "sem mexer nos outros" in msg


def test_meta_do_slide_deixa_margem_e_a_conferencia_cobre_a_rubrica_do_nivel(cfg):
    car = prompts.instrucao_formato("carrossel", cfg)
    assert f"no máximo {cfg['formatos']['carrossel']['caracteres_por_slide'] - 50} caracteres" in car
    inter = prompts.conferencia_final(ANCORA, "intermediario")
    assert "alocação e tendências" in inter and "renda fixa, renda variável ou câmbio" in inter and "um slide só para isso" in inter
    assert "o que muda no bolso" in prompts.conferencia_final(ANCORA, "iniciante")
    assert "implicação analítica" in prompts.conferencia_final(ANCORA, "avancado")


def test_cada_criterio_da_rubrica_reprovado_vem_com_a_frase_a_escrever():
    from avaliador.juiz import RUBRICA_POR_NIVEL
    from geracao.ramo import _dica_do_criterio
    for nivel, criterios in RUBRICA_POR_NIVEL.items():
        for c in criterios:
            assert _dica_do_criterio(c), (nivel, c)           # nenhum item da rubrica fica sem orientação
    aloc = _dica_do_criterio("O texto relaciona o documento a alocação e tendências.")
    assert "renda fixa" in aloc and "sem recomendar compra ou venda" in aloc and "um slide inteiro" in aloc
    assert _dica_do_criterio("critério qualquer") == ""
