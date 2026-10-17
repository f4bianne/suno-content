"""Adaptador de termo: normaliza o que a pessoa digitou e acha a fonte oficial (item 14)."""
import re
import time
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
    documento: str = ""          # nome do documento achado, por exemplo "Ata da 281ª reunião do Copom (16/09/2026)"


def canonico(termo: str, indice: glossario.Indice) -> str | None:
    """Nome do termo no glossário que corresponde ao texto digitado (sinônimos e plurais valem)."""
    achados = [o for o in indice.encontrar(termo, incluir_ambiguos=True)
               if normalizar(termo) == normalizar(termo[o.inicio:o.fim])]
    return achados[0].termo.termo if achados else None


def _recente_periodico(regras: dict, cliente: httpx.Client, hoje: date) -> tuple[str, str] | None:
    """(url, nome do documento) do período mais recente que existe."""
    for deslocamento in range(regras["anos_para_tras"] + 1):
        ano = hoje.year - deslocamento
        for mes in regras["meses"]:
            if ano == hoje.year and int(mes) > hoje.month:
                continue
            url = regras["url"].format(ano=ano, mes=mes)
            try:
                if cliente.head(url, follow_redirects=True, timeout=30).status_code == 200:
                    return url, regras["titulo"].format(ano=ano, mes=mes)
            except httpx.HTTPError:
                continue
    return None


def nome_da_ata(url: str) -> str:
    """'.../Copom281-not20260916281.pdf' -> 'Ata da 281ª reunião do Copom (16/09/2026)'."""
    m = re.search(r"Copom(\d+)-not(\d{4})(\d{2})(\d{2})", url)
    return f"Ata da {m[1]}ª reunião do Copom ({m[4]}/{m[3]}/{m[2]})" if m else "Ata do Copom"


def _ata_recente(regras: dict, cliente: httpx.Client, tentativas: int = 3, espera_s: float = 2.0) -> str | None:
    """A API do BC às vezes demora ou cai por alguns segundos: tenta de novo antes de desistir."""
    reunioes = None
    for n in range(tentativas):
        try:
            reunioes = cliente.get(regras["api"], timeout=30).json()["conteudo"]
            break
        except (httpx.HTTPError, ValueError, KeyError):
            if n < tentativas - 1:
                time.sleep(espera_s)
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
            url, nome = entrada["url"], entrada["nome"]
        elif entrada["fonte"] == "ata_copom_recente":
            url = _ata_recente(cfg["fontes_periodicas"]["ata_copom_recente"], cliente)
            nome = nome_da_ata(url) if url else ""
        else:
            url, nome = _recente_periodico(cfg["fontes_periodicas"][entrada["fonte"]], cliente, hoje or date.today()) or (None, "")
    finally:
        if dono:
            cliente.close()
    if not url:
        raise ErroIngestao(f"Não consegui localizar o documento mais recente para \"{termo}\".")
    return Resolucao(termo, chave, cano, entrada["nome"], url, nome)
