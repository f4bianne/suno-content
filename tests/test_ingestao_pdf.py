import copy
from pathlib import Path

import pytest

from avaliador import glossario
from ingestao import documento
from ingestao.documento import ErroIngestao
from ingestao.entrada import ingerir_pdf
from ingestao.pdf import parece_financeiro
from tests.pdfs import TEXTO_FINANCEIRO, TEXTO_RECEITA, pdf_minimo

CFG = documento.carregar_config()
RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def indice():
    return glossario.Indice(glossario.carregar())


def pdf_financeiro(paginas=1):
    return pdf_minimo([TEXTO_FINANCEIRO * 2 for _ in range(paginas)])


def test_normalizar_e_hash_ignoram_espacos():
    a = "Selic   subiu\r\n\r\n\r\n\r\npara 14,25%."
    b = "Selic subiu\n\npara 14,25%."
    assert documento.normalizar_texto(a) == b
    assert documento.hash_texto(a) == documento.hash_texto(b)
    assert documento.hash_texto("outro texto") != documento.hash_texto(a)


def test_pdf_financeiro_vira_documento(indice):
    dados = pdf_financeiro(2)
    d = ingerir_pdf(dados, "ata.pdf", indice)
    p = d.proveniencia
    assert d.paginas == 2 and "Selic" in d.texto
    assert p.tipo == "pdf" and p.origem == "ata.pdf" and p.sha256_bruto == documento.sha256_bytes(dados)
    assert d.chave == documento.hash_texto(d.texto)


def test_recusa_arquivo_que_nao_e_pdf(indice):
    with pytest.raises(ErroIngestao, match="não é um PDF"):
        ingerir_pdf(b"<html>oi</html>", "x.pdf", indice)


def test_recusa_pdf_grande_demais(indice):
    cfg = copy.deepcopy(CFG)
    cfg["pdf"]["tamanho_maximo_mb"] = 0.0001
    with pytest.raises(ErroIngestao, match="passa de"):
        ingerir_pdf(pdf_financeiro(), "x.pdf", indice, cfg)


def test_recusa_pdf_com_paginas_demais(indice):
    cfg = copy.deepcopy(CFG)
    cfg["pdf"]["paginas_maximas"] = 1
    with pytest.raises(ErroIngestao, match="2 páginas"):
        ingerir_pdf(pdf_financeiro(2), "x.pdf", indice, cfg)


def test_recusa_pdf_corrompido(indice):
    with pytest.raises(ErroIngestao):
        ingerir_pdf(b"%PDF-1.4 lixo", "x.pdf", indice)


def test_recusa_pdf_sem_texto(indice):
    with pytest.raises(ErroIngestao, match="quase não tem texto"):
        ingerir_pdf(pdf_minimo([["oi"]]), "x.pdf", indice)


def test_recusa_documento_que_nao_e_financeiro(indice):
    with pytest.raises(ErroIngestao, match="não parece financeiro"):
        ingerir_pdf(pdf_minimo([TEXTO_RECEITA * 3]), "receita.pdf", indice)


def test_sem_indice_nao_checa_assunto():
    assert ingerir_pdf(pdf_minimo([TEXTO_RECEITA * 3]), "receita.pdf").paginas == 1


def test_parece_financeiro_devolve_metricas(indice):
    ok, m = parece_financeiro(" ".join(TEXTO_FINANCEIRO), indice, CFG["pdf"]["financeiro"])
    assert ok and m["termos_distintos"] >= 6


@pytest.mark.skipif(not (RAIZ / "dados/corpus/atas_copom").exists(), reason="corpus não baixado")
def test_corpus_real_passa_na_checagem(indice):
    pdfs = sorted((RAIZ / "dados/corpus/atas_copom").glob("*.pdf"))[-1:]
    pdfs += sorted((RAIZ / "dados/corpus/cvm").glob("resolucao_175_parte_geral.pdf"))
    for arq in pdfs:
        d = ingerir_pdf(arq.read_bytes(), arq.name, indice)
        assert d.paginas > 1 and len(d.texto) > 5000
