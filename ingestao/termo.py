"""Adaptador de termo: normaliza o que a pessoa digitou e acha a fonte oficial (item 14)."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

import httpx

from avaliador import glossario
from ingestao.documento import ErroIngestao, carregar_config


def normalizar(termo: str) -> str:
    """Minúsculas, sem acento, sem pontuação e sem espaços repetidos."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", termo) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", sem_acento.lower())).strip()


@dataclass(frozen=True)
class Resolucao:
    termo_digitado: str
    termo_normalizado: str
    termo_canonico: str | None   # nome no glossário, se houver
    fonte: str                   # nome da fonte escolhida
    url: str                     # documento oficial a ingerir


def canonico(termo: str, indice: glossario.Indice) -> str | None:
    """Nome do termo no glossário que corresponde ao texto digitado (sinônimos e plurais valem)."""
    achados = [o for o in indice.encontrar(termo, incluir_ambiguos=True)
               if normalizar(termo) == normalizar(termo[o.inicio:o.fim])]
    return achados[0].termo.termo if achados else None


def _recente_periodico(regras: dict, cliente: httpx.Client, hoje: date) -> str | None:
    for deslocamento in range(regras["anos_para_tras"] + 1):
        ano = hoje.year - deslocamento
        for mes in regras["meses"]:
            if ano == hoje.year and int(mes) > hoje.month:
                continue
            url = regras["url"].format(ano=ano, mes=mes)
            try:
                if cliente.head(url, follow_redirects=True, timeout=30).status_code == 200:
                    return url
            except httpx.HTTPError:
                continue
    return None


def _ata_recente(regras: dict, cliente: httpx.Client) -> str | None:
    try:
        reunioes = cliente.get(regras["api"], timeout=30).json()["conteudo"]
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    if not reunioes:
        return None
    r = max(reunioes, key=lambda x: x["nroReuniao"])
    return regras["url"].format(nro=r["nroReuniao"], data=r["dataReferencia"].replace("-", ""))


def resolver(termo: str, indice: glossario.Indice | None = None, cfg: dict | None = None,
             cliente: httpx.Client | None = None, hoje: date | None = None) -> Resolucao:
    cfg = cfg or carregar_config()
    chave = normalizar(termo)
    if len(chave) < 2:
        raise ErroIngestao("Digite um termo com pelo menos duas letras.")
    cano = canonico(termo, indice) if indice else None
    candidatos = {chave} | ({normalizar(cano)} if cano else set())
    for entrada in cfg["termos"]:
        if candidatos & {normalizar(c) for c in entrada["chaves"]}:
            break
    else:
        raise ErroIngestao(f"Não há fonte oficial cadastrada para \"{termo}\". Tente enviar um PDF ou um link.")

    dono = cliente is None
    cliente = cliente or httpx.Client(headers={"User-Agent": "Mozilla/5.0"})
    try:
        if entrada["fonte"] == "url":
            url = entrada["url"]
        elif entrada["fonte"] == "ata_copom_recente":
            url = _ata_recente(cfg["fontes_periodicas"]["ata_copom_recente"], cliente)
        else:
            url = _recente_periodico(cfg["fontes_periodicas"][entrada["fonte"]], cliente, hoje or date.today())
    finally:
        if dono:
            cliente.close()
    if not url:
        raise ErroIngestao(f"Não consegui localizar o documento mais recente para \"{termo}\".")
    return Resolucao(termo, chave, cano, entrada["nome"], url)
