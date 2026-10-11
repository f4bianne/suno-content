"""Juiz LLM com rubrica estruturada. Usa outra família de modelos que o gerador (Groq, gpt-oss-120b)."""
import json
import os
import time
from pathlib import Path
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


def ler_env(nome: str, caminho: Path = Path(__file__).resolve().parent.parent / ".env") -> str | None:
    """Valor da variável de ambiente ou, na falta dela, da linha NOME=valor do arquivo .env."""
    if os.environ.get(nome):
        return os.environ[nome]
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            chave, _, valor = linha.partition("=")
            if chave.strip() == nome and valor.strip():
                return valor.strip().strip("\"'")
    return None


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


def schema_plano(modelo: type[BaseModel]) -> dict:
    """JSON Schema do modelo com as referências ($ref/$defs) substituídas pelo conteúdo, como o modo estrito pede."""
    bruto = modelo.model_json_schema()
    defs = bruto.pop("$defs", {})

    def resolver(no):
        if isinstance(no, dict):
            if "$ref" in no:
                return resolver(defs[no["$ref"].rsplit("/", 1)[-1]])
            return {k: resolver(v) for k, v in no.items()}
        if isinstance(no, list):
            return [resolver(v) for v in no]
        return no

    return resolver(bruto)


def post_com_retry(url: str, corpo: dict, cabecalhos: dict, tentativas: int = 6, espera_maxima_s: float = 60,
                   dormir=time.sleep) -> httpx.Response:
    """POST que espera e repete em 429 (limite de requisições) e 5xx, respeitando o cabeçalho retry-after."""
    for n in range(tentativas):
        r = httpx.post(url, json=corpo, headers=cabecalhos, timeout=180)
        if r.status_code != 429 and r.status_code < 500:
            r.raise_for_status()
            return r
        if n == tentativas - 1:
            r.raise_for_status()
        try:
            espera = float(r.headers.get("retry-after", ""))
        except ValueError:
            espera = 2.0 ** (n + 1)
        dormir(min(espera + 0.5, espera_maxima_s))
    raise RuntimeError("inalcançável")


class Cliente(Protocol):
    def completar_json(self, sistema: str, usuario: str, schema: dict) -> dict: ...


class ClienteGroq:
    """Chamada à API da Groq (compatível com OpenAI) pedindo JSON Schema estrito."""

    def __init__(self, modelo: str = MODELO_PADRAO, chave: str | None = None, temperatura: float = 0.0):
        self.modelo = modelo
        self.chave = chave or ler_env("GROQ_API_KEY")
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
        r = post_com_retry(URL_GROQ, corpo, {"Authorization": f"Bearer {self.chave}"})
        return json.loads(r.json()["choices"][0]["message"]["content"])


SISTEMA_JUIZ = (
    "Você é um revisor independente de conteúdo financeiro em português. Avalie o TEXTO apenas "
    "com base na ÂNCORA (fatos extraídos do documento oficial). Não use conhecimento externo "
    "para decidir se um FATO é verdadeiro. Seja rigoroso com fatos: liste em afirmacoes_sem_suporte "
    "toda afirmação que traga número, data, nome, decisão, projeção ou previsão que a âncora não sustenta.\n"
    "NÃO liste como sem suporte uma explicação ou consequência econômica geral e conhecida que decorre "
    "diretamente de um fato da âncora e não acrescenta número, data, nome, decisão ou previsão nova. "
    "Exemplo aceitável: com a âncora 'a Selic subiu', 'o crédito fica mais caro' é consequência geral. "
    "Exemplo a listar: 'a Selic vai chegar a 20%' ou 'o governo vai congelar preços'. "
    "Analogias e exemplos do dia a dia sem números também são aceitáveis.\n"
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
