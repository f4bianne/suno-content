"""Cliente da Anthropic (Claude) para o Extrator e o Gerador. Mesma interface do ClienteGroq."""
import json

from avaliador.juiz import ler_env, post_com_retry

MODELO_PADRAO = "claude-sonnet-5-5"
URL = "https://api.anthropic.com/v1/messages"


class ClienteAnthropic:
    """Pede a saída estruturada forçando o uso de uma ferramenta cujo input_schema é o schema desejado."""

    def __init__(self, modelo: str = MODELO_PADRAO, chave: str | None = None, temperatura: float = 0.0,
                 max_tokens: int = 4096):
        self.modelo, self.temperatura, self.max_tokens = modelo, temperatura, max_tokens
        self.chave = chave or ler_env("ANTHROPIC_API_KEY")
        if not self.chave:
            raise RuntimeError("defina ANTHROPIC_API_KEY no ambiente ou no .env")

    def completar_json(self, sistema: str, usuario: str, schema: dict) -> dict:
        corpo = {
            "model": self.modelo,
            "max_tokens": self.max_tokens,
            "temperature": self.temperatura,
            "system": sistema,
            "messages": [{"role": "user", "content": usuario}],
            "tools": [{"name": "saida", "description": "Devolve a resposta no formato pedido.", "input_schema": schema}],
            "tool_choice": {"type": "tool", "name": "saida"},
        }
        r = post_com_retry(URL, corpo, {"x-api-key": self.chave, "anthropic-version": "2023-06-01"})
        for bloco in r.json()["content"]:
            if bloco.get("type") == "tool_use":
                return bloco["input"]
        raise RuntimeError("a resposta não trouxe saída estruturada")


MODELO_GEMINI_PADRAO = "gemini-3.5-flash-lite"
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


class ClienteGemini:
    """Gemini (Google) pelo endpoint generateContent, pedindo JSON que obedeça ao schema."""

    def __init__(self, modelo: str = MODELO_GEMINI_PADRAO, chave: str | None = None, temperatura: float = 0.0):
        self.modelo, self.temperatura = modelo, temperatura
        self.chave = chave or ler_env("GEMINI_API_KEY")
        if not self.chave:
            raise RuntimeError("defina GEMINI_API_KEY no ambiente ou no .env")

    def completar_json(self, sistema: str, usuario: str, schema: dict) -> dict:
        corpo = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": usuario}]}],
            "generationConfig": {
                "temperature": self.temperatura,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        r = post_com_retry(URL_GEMINI.format(modelo=self.modelo), corpo, {"x-goog-api-key": self.chave})
        partes = r.json()["candidates"][0]["content"]["parts"]
        texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        return json.loads(texto)
