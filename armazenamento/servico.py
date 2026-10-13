"""Processa um documento usando o banco: devolve do cache quando da, senao gera, versiona e guarda (item 20)."""
import time
from typing import Callable

from avaliador import avaliar as av
from avaliador import glossario
from geracao import grafo
from geracao.schemas import FORMATOS
from ingestao.documento import Documento

from armazenamento import versoes
from armazenamento.repositorio import Repositorio


def processar_com_banco(documento: Documento, clientes: grafo.Clientes, indice: glossario.Indice, repo: Repositorio,
                        cfg: dict | None = None, niveis: tuple[str, ...] = av.NIVEIS, formatos: tuple[str, ...] = FORMATOS,
                        nivel_prioritario: str | None = None, max_tentativas: int = 3, concorrencia: int = 3,
                        max_fatos: int = 12, sessao: str | None = None, forcar: bool = False,
                        observador: Callable[[dict], None] | None = None) -> grafo.Processamento:
    cfg = cfg or av.carregar_config()
    documento_id = repo.salvar_documento(documento, sessao)
    snap = versoes.snapshot(clientes, cfg, max_tentativas, max_fatos)
    h = versoes.config_hash(snap)

    if not forcar:
        achado = repo.buscar_cache(documento_id, h, list(niveis), list(formatos))
        if achado:
            if observador:
                observador({"tipo": "cache", "execucao": achado})
            repo.registrar_acesso(documento_id, True, achado)
            return repo.abrir(achado, list(niveis), list(formatos), do_cache=True)

    t0 = time.time()
    proc = grafo.processar(documento, clientes, indice, cfg, niveis=niveis, formatos=formatos, nivel_prioritario=nivel_prioritario,
                           max_tentativas=max_tentativas, concorrencia=concorrencia, observador=observador, max_fatos=max_fatos)
    proc.config = snap
    proc.execucao_id = repo.salvar_execucao(documento_id, proc, snap, h, list(niveis), list(formatos), time.time() - t0)
    repo.registrar_acesso(documento_id, False, proc.execucao_id)
    return proc
