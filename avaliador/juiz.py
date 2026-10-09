"""Juiz LLM com rubrica estruturada. Usa outra família de modelos que o gerador (Groq, gpt-oss-120b)."""
import json
import os
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from avaliador.ancora import Ancora

MODELO_PADRAO = "openai/gpt-oss-120b"
URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"

RUBRICA_POR_NIVEL = {
    "iniciante": [
        "Cada conceito financeiro é traduzido em analogia do dia a dia (zero jargão desacompanhado de analogia).",
        "O texto diz o que muda para o bolso de quem lê.",
    ],
    "intermediario": [
        "O texto usa o vocabulário de mercado padrão sem didatismo infantil.",
        "O texto relaciona o documento a alocação e tendências.",
    ],
    "avancado": [
        "O texto preserva o jargão e a nuance do documento, sem simplificar nem infantilizar.",
        "O texto tem foco analítico e metodológico e explicita implicações que o documento só sugere, sem inventar.",
    ],
}


class Veredito(BaseModel):
    """Saída estruturada do Juiz. Sem valores padrão: o schema estrito exige todos os campos."""
    model_config = ConfigDict(extra="forbid")

    afirmacoes_sem_suporte: list[str] = Field(description="Afirmações do texto que a âncora não sustenta, copiadas do texto")
    nota_fidelidade: int = Field(description="1 = inventa fatos, 5 = tudo sustentado pela âncora")
    criterios_atendidos: list[str] = Field(description="Itens da rubrica do nível que o texto atende")
    criterios_nao_atendidos: list[str] = Field(description="Itens da rubrica do nível que o texto não atende")
    nota_adequacao_nivel: int = Field(description="1 = nível errado, 5 = nível exato")
    fatos_confirmados: list[str] = Field(description="Ids dos fatos indeterminados que o texto contém, mesmo com outras palavras")
    fatos_ausentes: list[str] = Field(description="Ids dos fatos indeterminados que o texto não contém")
    justificativa: str

    @field_validator("nota_fidelidade", "nota_adequacao_nivel")
    @classmethod
    def _nota_de_1_a_5(cls, v: int) -> int:
        # Validado aqui (e não no schema) porque o modo estrito da Groq aceita poucas palavras-chave.
        if not 1 <= v <= 5:
            raise ValueError("nota deve ir de 1 a 5")
        return v

    @property
    def aprovado(self) -> bool:
        return (not self.afirmacoes_sem_suporte and self.nota_fidelidade >= 4
                and not self.criterios_nao_atendidos and self.nota_adequacao_nivel >= 4)


class Cliente(Protocol):
    def completar_json(self, sistema: str, usuario: str, schema: dict) -> dict: ...


class ClienteGroq:
    """Chamada à API da Groq (compatível com OpenAI) pedindo JSON Schema estrito."""

    def __init__(self, modelo: str = MODELO_PADRAO, chave: str | None = None, temperatura: float = 0.0):
        self.modelo = modelo
        self.chave = chave or os.environ.get("GROQ_API_KEY")
        self.temperatura = temperatura
        if not self.chave:
            raise RuntimeError("defina GROQ_API_KEY no ambiente")

    def completar_json(self, sistema: str, usuario: str, schema: dict) -> dict:
        corpo = {
            "model": self.modelo,
            "temperature": self.temperatura,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "saida", "strict": True, "schema": schema}},
        }
        r = httpx.post(URL_GROQ, json=corpo, headers={"Authorization": f"Bearer {self.chave}"}, timeout=120)
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])


SISTEMA_JUIZ = (
    "Você é um revisor independente de conteúdo financeiro em português. Avalie o TEXTO apenas "
    "com base na ÂNCORA (fatos extraídos do documento oficial). Não use conhecimento externo. "
    "Seja rigoroso: qualquer afirmação não sustentada pela âncora deve ser listada. "
    "Nunca avalie se o texto é uma boa recomendação de investimento."
)


def montar_prompt(texto: str, nivel: str, formato: str, ancora: Ancora, indeterminados: list[str]) -> str:
    fatos = "\n".join(f"- [{f.id}] {f.texto}" for f in ancora.fatos)
    pendentes = ", ".join(indeterminados) or "(nenhum)"
    rubrica = "\n".join(f"- {c}" for c in RUBRICA_POR_NIVEL[nivel])
    return (
        f"NÍVEL ALVO: {nivel}\nFORMATO: {formato}\n\nÂNCORA:\n{fatos}\n\n"
        f"RUBRICA DO NÍVEL (copie os itens literalmente em criterios_atendidos ou criterios_nao_atendidos):\n{rubrica}\n\n"
        f"FATOS INDETERMINADOS (confirme em fatos_confirmados ou fatos_ausentes): {pendentes}\n\n"
        f"TEXTO:\n{texto}"
    )


def julgar(cliente: Cliente, texto: str, nivel: str, formato: str, ancora: Ancora,
           indeterminados: list[str] | None = None) -> Veredito:
    schema = Veredito.model_json_schema()
    bruto = cliente.completar_json(SISTEMA_JUIZ, montar_prompt(texto, nivel, formato, ancora, indeterminados or []), schema)
    return Veredito.model_validate(bruto)
