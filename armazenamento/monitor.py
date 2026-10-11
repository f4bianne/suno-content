"""Monitor de fontes oficiais: descobre documentos novos e diz quais ainda nao estao no banco (item 21).

Nao ha agendador: o monitor roda sob demanda (`python scripts/monitor.py`) e, em producao, pode ser chamado por
um cron. Ele so decide o que e novo; quem gera e `processar_com_banco`.
"""
from dataclasses import dataclass

import httpx

from armazenamento.repositorio import Repositorio
from avaliador import glossario
from ingestao import termo
from ingestao.documento import ErroIngestao, carregar_config


@dataclass(frozen=True)
class Fonte:
    nome: str
    termo: str          # termo que resolve para essa fonte
    url: str | None     # None quando nao foi possivel localizar o documento
    nova: bool          # a URL ainda nao esta no banco
    erro: str | None = None


def verificar(repo: Repositorio, indice: glossario.Indice | None = None, cfg: dict | None = None,
              cliente: httpx.Client | None = None) -> list[Fonte]:
    cfg = cfg or carregar_config()
    dono = cliente is None
    cliente = cliente or httpx.Client(headers={"User-Agent": "Mozilla/5.0"})
    achadas: list[Fonte] = []
    try:
        for entrada in cfg["termos"]:
            consulta = entrada["chaves"][0]
            try:
                r = termo.resolver(consulta, indice, cfg, cliente)
            except ErroIngestao as e:
                achadas.append(Fonte(entrada["nome"], consulta, None, False, str(e)))
                continue
            achadas.append(Fonte(entrada["nome"], consulta, r.url, not repo.url_conhecida(r.url)))
    finally:
        if dono:
            cliente.close()
    return achadas
