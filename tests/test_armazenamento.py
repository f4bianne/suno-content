import pytest

from armazenamento import versoes
from armazenamento.repositorio import Repositorio
from armazenamento.servico import processar_com_banco
from avaliador import avaliar as av
from avaliador import glossario
from geracao import grafo
from ingestao.documento import Documento, Proveniencia
from tests.fixtures_geracao import ANCORA, GeradorFalso, JuizFalso
from tests.test_api import ExtratorFalso, TEXTO


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


@pytest.fixture()
def cfg():
    c = av.carregar_config()
    c["formatos"]["artigo"]["palavras"] = [20, 900]
    return c


def doc(tipo="termo", texto=TEXTO, origem="Copom"):
    return Documento(texto=texto, proveniencia=Proveniencia(tipo=tipo, origem=origem, url="https://x/ata.pdf" if tipo != "pdf" else None,
                                                            sha256_bruto="0" * 64))


def clientes(gerador=None, modelo="m1"):
    g = gerador or GeradorFalso(0)
    g.modelo = modelo
    return grafo.Clientes(extrator=ExtratorFalso(), gerador=g, juiz=JuizFalso())


def rodar(repo, indice, cfg, d=None, cl=None, **kw):
    return processar_com_banco(d or doc(), cl or clientes(), indice, repo, cfg, **kw)


def test_execucao_e_gravada_e_reaberta_igual(indice, cfg):
    repo = Repositorio("sqlite://")
    p = rodar(repo, indice, cfg)
    assert p.execucao_id and not p.do_cache and len(p.ramos) == 9
    r = repo.abrir(p.execucao_id)
    assert [(x.nivel, x.formato, x.status, len(x.tentativas)) for x in r.ramos] == \
           [(x.nivel, x.formato, x.status, len(x.tentativas)) for x in p.ramos]
    assert r.ancora.fatos[0].numeros == ["14,25"] and r.config == p.config
    assert r.ramos[0].tentativas[0].metricas["flesch"] == p.ramos[0].tentativas[0].metricas["flesch"]


def test_segunda_chamada_sai_do_cache_sem_chamar_modelos(indice, cfg):
    repo, g = Repositorio("sqlite://"), GeradorFalso(0)
    primeira = rodar(repo, indice, cfg, cl=clientes(g))
    chamadas = sum(g.chamadas.values())
    eventos = []
    segunda = rodar(repo, indice, cfg, cl=clientes(g), observador=eventos.append)
    assert segunda.do_cache and segunda.execucao_id == primeira.execucao_id
    assert sum(g.chamadas.values()) == chamadas          # nenhuma chamada nova ao gerador
    assert eventos == [{"tipo": "cache", "execucao": primeira.execucao_id}]
    assert len(repo.listar()) == 1


def test_cada_geracao_aparece_pelo_que_foi_pesquisado(indice, cfg):
    """Pesquisar "taxa selic" depois de "Copom" mostrava "Copom": o registro do documento guarda a primeira busca."""
    repo = Repositorio("sqlite://")
    rodar(repo, indice, cfg, d=doc(origem="Copom"))
    selic = doc(origem="taxa selic")
    selic.proveniencia.documento = "Ata da 281ª reunião do Copom (16/09/2026)"
    cache = rodar(repo, indice, cfg, d=selic)
    assert cache.do_cache and cache.origem == "taxa selic" and cache.documento_nome == "Ata da 281ª reunião do Copom (16/09/2026)"
    nova = rodar(repo, indice, cfg, d=selic, forcar=True)
    lista = repo.listar()
    assert [x["origem"] for x in lista] == ["taxa selic", "Copom"] and lista[0]["tipo"] == "termo"
    assert lista[0]["documento_nome"] == "Ata da 281ª reunião do Copom (16/09/2026)"
    assert repo.abrir(nova.execucao_id).origem == "taxa selic"
    assert len({x["documento"] for x in lista}) == 1                    # o documento continua um só no banco


def test_link_e_pdf_aparecem_pelo_link_e_pelo_nome_do_arquivo(indice, cfg):
    repo = Repositorio("sqlite://")
    rodar(repo, indice, cfg, d=doc(tipo="link", origem="https://www.bcb.gov.br/ata.pdf"))
    rodar(repo, indice, cfg, d=doc(tipo="pdf", texto=TEXTO + " outro", origem="ata_copom.pdf"), sessao="s1")
    por_tipo = {x["tipo"]: x["origem"] for x in repo.listar("s1")}
    assert por_tipo == {"link": "https://www.bcb.gov.br/ata.pdf", "pdf": "ata_copom.pdf"}


def test_forcar_gera_outra_versao_sem_apagar_a_anterior(indice, cfg):
    repo = Repositorio("sqlite://")
    a = rodar(repo, indice, cfg)
    b = rodar(repo, indice, cfg, forcar=True)
    assert a.execucao_id != b.execucao_id and not b.do_cache
    assert len(repo.listar()) == 2 and repo.abrir(a.execucao_id) is not None


@pytest.mark.parametrize("mudanca", ["modelo", "tentativas", "avaliacao"])
def test_configuracao_diferente_nao_reaproveita_o_cache(indice, cfg, mudanca):
    repo = Repositorio("sqlite://")
    a = rodar(repo, indice, cfg)
    if mudanca == "modelo":
        b = rodar(repo, indice, cfg, cl=clientes(modelo="outro-modelo"))
    elif mudanca == "tentativas":
        b = rodar(repo, indice, cfg, max_tentativas=5)
    else:
        outra = av.carregar_config()
        outra["formatos"]["artigo"]["palavras"] = [30, 900]
        b = rodar(repo, indice, outra)
    assert not b.do_cache and b.execucao_id != a.execucao_id and b.config != a.config


def test_pedido_menor_e_atendido_pelo_cache_maior(indice, cfg):
    repo = Repositorio("sqlite://")
    cheio = rodar(repo, indice, cfg)
    parte = rodar(repo, indice, cfg, niveis=("iniciante",), formatos=("artigo",))
    assert parte.do_cache and parte.execucao_id == cheio.execucao_id
    assert [(r.nivel, r.formato) for r in parte.ramos] == [("iniciante", "artigo")]


def test_pedido_maior_nao_e_atendido_por_cache_menor(indice, cfg):
    repo = Repositorio("sqlite://")
    rodar(repo, indice, cfg, niveis=("iniciante",), formatos=("artigo",))
    cheio = rodar(repo, indice, cfg)
    assert not cheio.do_cache and len(cheio.ramos) == 9


def test_documento_diferente_nao_cai_no_cache(indice, cfg):
    repo = Repositorio("sqlite://")
    rodar(repo, indice, cfg)
    outro = rodar(repo, indice, cfg, d=doc(texto=TEXTO + " O comitê segue atento."))
    assert not outro.do_cache


def test_pdf_e_privado_da_sessao_e_fonte_oficial_e_publica(indice, cfg):
    repo = Repositorio("sqlite://")
    publico = rodar(repo, indice, cfg, d=doc("termo"))
    privado = rodar(repo, indice, cfg, d=doc("pdf", origem="meu.pdf"), sessao="ana")
    assert repo.pode_ver(publico.execucao_id, None) and repo.pode_ver(publico.execucao_id, "bia")
    assert repo.pode_ver(privado.execucao_id, "ana")
    assert not repo.pode_ver(privado.execucao_id, "bia") and not repo.pode_ver(privado.execucao_id, None)
    assert {x["id"] for x in repo.listar("ana")} == {publico.execucao_id, privado.execucao_id}
    assert {x["id"] for x in repo.listar("bia")} == {publico.execucao_id}
    assert {x["id"] for x in repo.listar()} == {publico.execucao_id}


def test_mesmo_pdf_em_sessoes_diferentes_nao_compartilha_cache(indice, cfg):
    repo = Repositorio("sqlite://")
    a = rodar(repo, indice, cfg, d=doc("pdf", origem="x.pdf"), sessao="ana")
    b = rodar(repo, indice, cfg, d=doc("pdf", origem="x.pdf"), sessao="bia")
    assert not b.do_cache and a.execucao_id != b.execucao_id


def test_snapshot_identifica_modelos_prompts_glossario_e_codigo(cfg):
    s = versoes.snapshot(clientes(modelo="gemini-x"), cfg, 3, 12)
    assert s["modelos"]["gerador"] == "gemini-x"
    assert set(s["prompts"]) == {"extrator", "juiz", "gerador"} and all(len(v) == 12 for v in s["prompts"].values())
    assert len(s["glossario"]) == 12 and len(s["avaliacao"]) == 12 and len(s["codigo"]) == 12
    assert versoes.config_hash(s) == versoes.config_hash(dict(s))
    assert versoes.config_hash({**s, "max_tentativas": 4}) != versoes.config_hash(s)


def test_glossario_alterado_muda_a_versao(cfg, tmp_path):
    alterado = tmp_path / "glossario.yaml"
    alterado.write_bytes((versoes.RAIZ / "dados" / "glossario.yaml").read_bytes() + b"\n# mudou\n")
    a = versoes.snapshot(clientes(), cfg, 3, 12)
    b = versoes.snapshot(clientes(), cfg, 3, 12, caminho_glossario=alterado)
    assert a["glossario"] != b["glossario"] and versoes.config_hash(a) != versoes.config_hash(b)


def test_dados_persistem_no_arquivo(indice, cfg, tmp_path):
    url = f"sqlite:///{(tmp_path / 'suno.db').as_posix()}"
    p = rodar(Repositorio(url), indice, cfg)
    de_novo = Repositorio(url)                      # processo novo, mesmo arquivo
    assert de_novo.abrir(p.execucao_id).ancora.fatos
    assert rodar(de_novo, indice, cfg).do_cache


def test_url_conhecida_para_o_monitor(indice, cfg):
    repo = Repositorio("sqlite://")
    assert not repo.url_conhecida("https://x/ata.pdf")
    rodar(repo, indice, cfg)
    assert repo.url_conhecida("https://x/ata.pdf")
    rodar(repo, indice, cfg, d=doc("pdf", origem="y.pdf"), sessao="ana")
    assert not repo.url_conhecida("y.pdf")           # upload privado nunca conta como fonte oficial


def test_abrir_execucao_inexistente():
    assert Repositorio("sqlite://").abrir("nada") is None
