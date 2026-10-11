"""Documento normalizado e proveniência (roadmap, itens 12 a 15)."""
import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

CONFIG_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "ingestao.yaml"


def carregar_config(caminho: Path = CONFIG_PADRAO) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


class ErroIngestao(Exception):
    """Entrada recusada. A mensagem pode ser mostrada ao visitante."""


class Proveniencia(BaseModel):
    tipo: Literal["pdf", "link", "termo"]
    origem: str                      # nome do arquivo, URL ou termo digitado
    url: str | None = None           # URL final (links e termos resolvidos)
    coletado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sha256_bruto: str                # hash dos bytes baixados ou enviados


class Documento(BaseModel):
    titulo: str | None = None
    texto: str
    paginas: int | None = None
    tabelas: list[str] = []
    proveniencia: Proveniencia

    @property
    def chave(self) -> str:
        """Identifica o conteúdo, não a porta de entrada: o mesmo texto vindo de PDF e de link tem a mesma chave."""
        return hash_texto(self.texto)


def sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def normalizar_texto(texto: str) -> str:
    """NFC, sem caracteres de controle, espaços e quebras de linha enxutos."""
    texto = unicodedata.normalize("NFC", texto).replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", texto)
    texto = re.sub(r"[ \t ]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def hash_texto(texto: str) -> str:
    return sha256_bytes(normalizar_texto(texto).encode("utf-8"))
