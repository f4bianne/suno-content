"""Conteúdos de exemplo que passam no avaliador, um por nível e formato, e geradores falsos para os testes."""
from avaliador.ancora import Ancora, Fato

ANCORA = Ancora(fatos=[
    Fato(id="f1", texto="O Copom elevou a Selic para 14,25% ao ano", numeros=["14,25"], entidades=["Selic"]),
    Fato(id="f2", texto="A inflação em 12 meses medida pelo IPCA foi de 5,06%", numeros=["5,06"], entidades=["IPCA"]),
    Fato(id="f3", texto="O comitê vê incerteza elevada no cenário externo"),
])

# Falas e textos por nível (cada nível tem vocabulário e comprimento de frase próprios).
TEXTOS = {
    "iniciante": [
        "A Selic, que é a taxa básica de juros, subiu para 14,25% ao ano.",
        "Isso deixa o crédito mais caro.",
        "A inflação em 12 meses foi de 5,06%.",
        "Ou seja, os preços sobem mais do que o previsto.",
        "Lá fora, a incerteza segue alta.",
    ],
    "intermediario": [
        "O Copom elevou a Selic para 14,25% ao ano, em um cenário no qual a inflação acumulada em doze meses, medida pelo IPCA, "
        "chegou a 5,06%, valor que permanece acima da meta estabelecida e reforça a necessidade de cautela na política monetária.",
        "O comitê enxerga incerteza elevada no cenário externo, circunstância que pesa sobre a trajetória dos juros e sobre as "
        "decisões de alocação dos investidores durante os próximos trimestres.",
    ],
    "avancado": [
        "O Copom elevou a Selic a 14,25% ao ano, decisão compatível com a convergência da inflação, medida pelo IPCA em 5,06% no "
        "acumulado de doze meses, para o redor da meta ao longo do horizonte relevante, em um contexto de balanço de riscos "
        "assimétrico, desancoragem das expectativas de inflação e incerteza elevada no cenário externo, circunstâncias que "
        "sustentam uma política monetária restritiva durante período prolongado.",
    ],
}
# Frases menores, para slides (até 220 caracteres) e cenas de vídeo.
CURTAS = {
    "iniciante": TEXTOS["iniciante"],
    "intermediario": [
        "O Copom elevou a Selic para 14,25% ao ano, em um cenário de inflação persistentemente acima da meta estabelecida, o que reforça a necessidade de cautela.",
        "A inflação acumulada em doze meses, medida pelo IPCA, chegou a 5,06%, valor que permanece incompatível com os objetivos da política monetária adotada.",
        "O comitê enxerga incerteza elevada no cenário externo, circunstância que pesa sobre a trajetória dos juros e sobre as decisões de alocação.",
    ],
    "avancado": [
        "O Copom elevou a Selic a 14,25% ao ano, decisão compatível com a estratégia de convergência da inflação para o redor da meta ao longo do horizonte relevante.",
        "A inflação, medida pelo IPCA em 5,06% no acumulado de doze meses, mantém o balanço de riscos assimétrico, sobretudo diante da desancoragem das expectativas.",
        "A incerteza elevada no cenário externo e a desancoragem das expectativas sustentam uma política monetária restritiva durante período prolongado.",
    ],
}
# Falas de vídeo: frases mais curtas que as dos slides, porque são lidas em voz alta.
VIDEO = dict(CURTAS, intermediario=[
    "O Copom elevou a Selic para 14,25% ao ano, em um cenário de inflação acima da meta estabelecida.",
    "A inflação acumulada em doze meses, medida pelo IPCA, chegou a 5,06%, o que reforça a necessidade de cautela.",
    "O comitê enxerga incerteza elevada no cenário externo, circunstância que pesa sobre as decisões de alocação.",
])
GANCHO = {"iniciante": "Seu crédito vai ficar mais caro?", "intermediario": "Selic a 14,25%: o que muda na alocação?",
          "avancado": "Selic a 14,25% e a assimetria do balanço de riscos"}
CONCLUSAO = {"iniciante": "Por isso vale acompanhar o preço do dinheiro.",
             "intermediario": "O comitê sinaliza prudência na condução da política monetária nos próximos meses.",
             "avancado": "A condução dependerá da evolução das expectativas e do cenário externo, segundo o comitê."}


def bom(nivel: str, formato: str) -> dict:
    """Resposta do LLM (no schema do formato) que o avaliador aprova."""
    if formato == "artigo":
        return {"titulo": GANCHO[nivel], "corpo": " ".join(TEXTOS[nivel]), "conclusao": CONCLUSAO[nivel]}
    frases = CURTAS[nivel]
    if formato == "carrossel":
        return {"gancho": GANCHO[nivel], "slides_corpo": frases[:4] if nivel == "iniciante" else [*frases, frases[0]],
                "conclusao": CONCLUSAO[nivel]}
    cenas, t = [], 0
    for i, f in enumerate(VIDEO[nivel][:3]):
        cenas.append({"inicio_s": t, "fim_s": t + 15, "fala": f, "visual": "seta para cima sobre a taxa" if i == 0 else "gráfico"})
        t += 15
    return {"cenas": cenas}


def ruim(nivel: str, formato: str) -> dict:
    """Mesma estrutura, mas com jargão pesado e número inventado: reprova em qualquer nível menos o avançado."""
    texto = str(bom("avancado", formato)).replace("14,25%", "13,10%")
    return eval(texto) if nivel == "avancado" else bom("avancado", formato)


def nivel_e_formato(sistema: str) -> tuple[str, str]:
    nivel = "iniciante" if "iniciantes" in sistema else "intermediario" if "intermediários" in sistema else "avancado"
    formato = "artigo" if "FORMATO: artigo" in sistema else "carrossel" if "FORMATO: carrossel" in sistema else "video"
    return nivel, formato


class GeradorFalso:
    """Devolve `ruim` nas primeiras `falhas` chamadas de cada ramo e `bom` depois. Guarda os prompts recebidos."""

    def __init__(self, falhas_antes_de_acertar: int = 0):
        self.falhas, self.chamadas, self.prompts = falhas_antes_de_acertar, {}, []

    def completar_json(self, sistema, usuario, schema):
        chave = nivel_e_formato(sistema)
        self.prompts.append((chave, usuario))
        self.chamadas[chave] = self.chamadas.get(chave, 0) + 1
        return (ruim if self.chamadas[chave] <= self.falhas else bom)(*chave)


class JuizFalso:
    def __init__(self, aprovar=True, rejeitar_primeiras=0):
        self.aprovar, self.rejeitar, self.n = aprovar, rejeitar_primeiras, 0

    def completar_json(self, sistema, usuario, schema):
        self.n += 1
        rejeita = (not self.aprovar) or self.n <= self.rejeitar
        return {
            "afirmacoes_sem_suporte": ["A Selic vai a 20%"] if rejeita else [],
            "nota_fidelidade": 2 if rejeita else 5,
            "criterios_atendidos": [], "criterios_nao_atendidos": [],
            "nota_adequacao_nivel": 5,
            "fatos_confirmados": ["f3"], "fatos_ausentes": [], "justificativa": "teste",
        }
