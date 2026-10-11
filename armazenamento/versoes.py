"""Identificacao completa de uma execucao: modelos, prompts, glossario, regras e codigo (item 22).

O `config_hash` e a chave do cache: so ha cache quando o documento e TODA essa configuracao sao iguais.
Mudou um prompt, o glossario, uma faixa do avaliador ou uma linha do codigo, e o resultado antigo nao vale.
"""
import hashlib
import json
from pathlib import Path

from avaliador import juiz
from ingestao import extrator

RAIZ = Path(__file__).resolve().parent.parent
PASTAS_DO_CODIGO = ("avaliador", "geracao", "ingestao")


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()[:12]


def hash_do_codigo() -> str:
    """Hash do conteudo dos .py que influenciam o resultado."""
    h = hashlib.sha256()
    for pasta in PASTAS_DO_CODIGO:
        for arq in sorted((RAIZ / pasta).glob("*.py")):
            h.update(arq.name.encode())
            h.update(arq.read_bytes())
    return h.hexdigest()[:12]


def _modelo(cliente) -> str:
    return getattr(cliente, "modelo", type(cliente).__name__)


def snapshot(clientes, cfg_avaliacao: dict, max_tentativas: int, max_fatos: int, caminho_glossario: Path | None = None) -> dict:
    """Foto da configuracao usada, gravada junto de cada execucao."""
    glossario = caminho_glossario or RAIZ / "dados" / "glossario.yaml"
    return {
        "modelos": {"extrator": _modelo(clientes.extrator), "gerador": _modelo(clientes.gerador), "juiz": _modelo(clientes.juiz)},
        "prompts": {
            "extrator": _sha(extrator.SISTEMA.encode()),
            "juiz": _sha((juiz.SISTEMA_JUIZ + json.dumps(juiz.RUBRICA_POR_NIVEL, sort_keys=True)).encode()),
            "gerador": _sha((RAIZ / "geracao" / "prompts.py").read_bytes()),
        },
        "glossario": _sha(glossario.read_bytes()),
        "avaliacao": _sha(json.dumps(cfg_avaliacao, sort_keys=True, default=str).encode()),
        "max_tentativas": max_tentativas,
        "max_fatos": max_fatos,
        "codigo": hash_do_codigo(),
    }


def config_hash(snap: dict) -> str:
    return _sha(json.dumps(snap, sort_keys=True).encode())
