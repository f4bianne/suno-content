from collections import defaultdict
from pathlib import Path

import yaml

CAMINHO = Path(__file__).resolve().parent.parent / "dados" / "glossario.yaml"
OBRIGATORIOS = {"termo", "nivel", "categoria", "fonte", "explicacao_curta"}
PERMITIDOS = OBRIGATORIOS | {"variantes", "ambiguo", "docs_corpus"}


def carregar():
    with CAMINHO.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def formas(entrada):
    return [entrada["termo"], *entrada.get("variantes", [])]


def chave(forma):
    # Siglas (tudo em maiúsculas) diferenciam a caixa; o resto não.
    return forma if forma.isupper() else forma.lower()


def test_campos_obrigatorios_e_desconhecidos():
    for e in carregar()["termos"]:
        assert OBRIGATORIOS <= e.keys(), f"campos faltando em {e.get('termo')}"
        assert e.keys() <= PERMITIDOS, f"campo desconhecido em {e['termo']}"


def test_nivel_valido():
    for e in carregar()["termos"]:
        assert e["nivel"] in (1, 2, 3), e["termo"]


def test_fonte_existe():
    dados = carregar()
    for e in dados["termos"]:
        assert e["fonte"] in dados["fontes"], f"{e['termo']}: fonte {e['fonte']} desconhecida"


def test_fontes_com_url_publica():
    for nome, f in carregar()["fontes"].items():
        assert f["nome"], nome
        assert f["url"] is None or f["url"].startswith("https://"), nome


def test_explicacao_nao_vazia():
    for e in carregar()["termos"]:
        assert e["explicacao_curta"].strip(), e["termo"]


def test_forma_nao_repetida_entre_termos():
    donos = defaultdict(set)
    for e in carregar()["termos"]:
        for forma in formas(e):
            donos[chave(forma)].add(e["termo"])
    repetidas = {k: v for k, v in donos.items() if len(v) > 1}
    assert not repetidas, f"forma em mais de um termo: {repetidas}"


def test_termo_canonico_unico():
    nomes = [chave(e["termo"]) for e in carregar()["termos"]]
    assert len(nomes) == len(set(nomes))


def test_ancoras_do_case():
    # Definições do case: nível 2 = CDI, Selic, IPCA, dividendos;
    # nível 3 = curva de juros, forward guidance, hiato do produto, EBITDA ajustado, covenants.
    nivel = {chave(f): e["nivel"] for e in carregar()["termos"] for f in formas(e)}
    for termo in ("CDI", "selic", "IPCA", "dividendos"):
        assert nivel[chave(termo)] == 2, termo
    for termo in ("curva de juros", "forward guidance", "hiato do produto", "EBITDA ajustado", "covenants"):
        assert nivel[chave(termo)] == 3, termo
