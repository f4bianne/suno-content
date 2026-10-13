import pytest

from armazenamento import relatorios
from armazenamento.repositorio import Repositorio
from avaliador import avaliar as av
from avaliador import glossario
from tests.fixtures_geracao import GeradorFalso
from tests.test_armazenamento import clientes, doc
from armazenamento.servico import processar_com_banco


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


@pytest.fixture()
def cfg():
    c = av.carregar_config()
    c["formatos"]["artigo"]["palavras"] = [20, 900]
    return c


def gerar(repo, indice, cfg, falhas=0, d=None, **kw):
    return processar_com_banco(d or doc(), clientes(GeradorFalso(falhas)), indice, repo, cfg, **kw)


def test_carregar_traz_ramos_e_tentativas(indice, cfg):
    repo = Repositorio("sqlite://")
    p = gerar(repo, indice, cfg, falhas=1)
    regs = relatorios.carregar(repo)
    assert len(regs) == 9 and all(r.execucao_id == p.execucao_id and r.origem == "Copom" for r in regs)
    assert all(len(r.tentativas) == 2 for r in regs)
    assert relatorios.carregar(repo, ["nao-existe"]) == []


def test_matriz_antes_e_depois_do_loop(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg, falhas=1)   # 1a tentativa ruim (jargao/numero errado), 2a boa
    regs = relatorios.carregar(repo)
    antes = relatorios.matriz(regs, "antes", indice)
    depois = relatorios.matriz(regs, "depois", indice)
    assert antes["n"] == depois["n"] == 9
    assert depois["acuracia"] == 1.0                       # os textos de exemplo de cada nivel sao reconhecidos
    assert antes["acuracia"] < depois["acuracia"]          # o loop melhorou a distincao dos niveis
    assert all(depois["matriz"][n][n] == 3 for n in relatorios.NIVEIS)


def test_matriz_por_formato_e_so_aprovados(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg)
    regs = relatorios.carregar(repo)
    assert relatorios.matriz(regs, "depois", indice, formato="video")["n"] == 3
    assert relatorios.matriz(regs, "depois", indice, so_aprovados=True)["n"] == 9


def test_matriz_ignora_ramo_sem_conteudo(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg)
    regs = relatorios.carregar(repo)
    regs[0].tentativas = [dict(t, conteudo=None) for t in regs[0].tentativas]
    regs[0].conteudo_final = None
    m = relatorios.matriz(regs, "antes", indice)
    assert m["n"] == 8 and m["sem_conteudo"] == 1


def test_matriz_com_classificador_llm_usa_o_cliente(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg)
    chamadas = []

    class ClienteSempreAvancado:
        def completar_json(self, sistema, usuario, schema):
            chamadas.append(usuario)
            return {"nivel": "avancado", "justificativa": "teste"}

    m = relatorios.matriz(relatorios.carregar(repo), "depois", indice, cliente_llm=ClienteSempreAvancado())
    assert len(chamadas) == 9 and all(m["matriz"][n]["avancado"] == 3 for n in relatorios.NIVEIS)
    assert m["acuracia"] == pytest.approx(1 / 3)


def test_convergencia_e_custo(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg, falhas=1)
    cc = relatorios.convergencia_e_custo(relatorios.carregar(repo))
    t = cc["total"]
    assert t["ramos"] == 9 and t["aprovados"] == 9 and t["taxa_aprovacao"] == 1.0
    assert t["aprovou_na_primeira"] == 0.0 and t["recuperados_pelo_loop"] == 9 and t["tentativas_media"] == 2.0
    assert set(cc["por_nivel"]) == set(relatorios.NIVEIS) and set(cc["por_formato"]) == set(relatorios.FORMATOS)
    assert cc["por_nivel"]["iniciante"]["ramos"] == 3


def test_flesch_por_nivel_cai_do_iniciante_ao_avancado(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg)
    f = relatorios.flesch_por_nivel(relatorios.carregar(repo))
    assert f["iniciante"] > f["intermediario"] > f["avancado"]


def test_acessos_ao_cache_sao_contados(indice, cfg):
    repo = Repositorio("sqlite://")
    assert repo.taxa_de_cache() == (0, 0)
    gerar(repo, indice, cfg)
    gerar(repo, indice, cfg)       # acerta o cache
    gerar(repo, indice, cfg)       # acerta o cache
    gerar(repo, indice, cfg, forcar=True)
    assert repo.taxa_de_cache() == (2, 4)
    r = relatorios.execucoes_resumo(repo)
    assert r["execucoes"] == 2 and r["acessos"] == 4 and r["acertos_de_cache"] == 2


def test_relatorio_markdown_completo(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg, falhas=1)
    gerar(repo, indice, cfg)
    md = relatorios.relatorio_markdown(repo, indice)
    for trecho in ("Matriz de confusao", "Antes do loop", "Depois do loop", "Por formato", "Flesch medio", "Convergencia, custo e latencia",
                   "Taxa de acerto do cache", "Limite:", "Acuracia"):
        assert trecho in md, trecho
    assert "regras" in md and "LLM" not in md.split("Limite:")[0]


def test_relatorio_sem_dados():
    assert relatorios.relatorio_markdown(Repositorio("sqlite://"), glossario.Indice(glossario.carregar())) == "Nenhuma execucao no banco."


def test_texto_do_conteudo_dos_tres_formatos():
    assert relatorios.texto_do_conteudo("artigo", {"titulo": "T", "corpo": "C", "conclusao": "F"}) == "T\nC\nF"
    assert relatorios.texto_do_conteudo("carrossel", {"slides": ["a", "b"]}) == "a\nb"
    assert relatorios.texto_do_conteudo("video", {"cenas": [{"inicio_s": 0, "fim_s": 5, "fala": "oi", "visual": "x"}]}) == "oi"


def test_cliente_com_cache_classifica_cada_texto_uma_vez():
    chamadas = []

    class Base:
        def completar_json(self, sistema, usuario, schema):
            chamadas.append(usuario)
            return {"nivel": "iniciante", "justificativa": "x"}

    c = relatorios.ClienteComCache(Base())
    for _ in range(3):
        c.completar_json("s", "texto A", {})
    c.completar_json("s", "texto B", {})
    assert len(chamadas) == 2 and c.chamadas == 2


def test_relatorio_com_llm_nao_repete_chamadas(indice, cfg):
    repo = Repositorio("sqlite://")
    gerar(repo, indice, cfg)

    class Base:
        n = 0

        def completar_json(self, sistema, usuario, schema):
            Base.n += 1
            return {"nivel": "avancado", "justificativa": "x"}

    cliente = relatorios.ClienteComCache(Base())
    relatorios.relatorio_markdown(repo, indice, cliente_llm=cliente)
    # 9 ramos, 1a tentativa aprovada = mesmo texto antes e depois, entao so 9 textos unicos, nao ~45 chamadas
    assert Base.n == 9
