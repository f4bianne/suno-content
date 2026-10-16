"""Agente Revisor: lê o que o avaliador reprovou e escreve o plano de reescrita da próxima tentativa.

O avaliador diz o que está errado (métricas e frases soltas). O gerador, sozinho, costuma corrigir um problema e abrir
outro. O revisor fica entre os dois: recebe o texto, os fatos e as falhas e devolve ações concretas e ordenadas, dizendo
também o que deve ser preservado. Se ele falhar, a reescrita segue só com o relatório de falhas.
"""
import re

from pydantic import BaseModel, ConfigDict

from avaliador.ancora import Ancora
from avaliador.glossario import Termo
from avaliador.juiz import Cliente, schema_plano


class PlanoLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagnostico: str        # a causa principal, em uma frase
    acoes: list[str]        # edições concretas, da mais importante para a menos
    manter: list[str]       # o que já está certo e não deve mudar


SISTEMA = (
    "Você é o revisor editorial de um sistema que adapta documentos financeiros oficiais para três níveis de leitor. "
    "Você NÃO reescreve o texto. Você recebe uma versão reprovada, os fatos permitidos e as falhas apontadas pelo "
    "avaliador, e escreve o plano para a próxima tentativa.\n"
    "REGRAS DO PLANO:\n"
    "- diagnostico: a causa principal das reprovações, em uma frase.\n"
    "- acoes: no máximo 6, da mais importante para a menos, cada uma concreta e verificável. Diga ONDE mexer (qual cena, "
    "slide ou parágrafo), O QUE fazer e COM QUAIS PALAVRAS quando for explicar um termo ou inserir um fato. Cite fatos pelo "
    "id e pelo número exato que consta nos fatos. Uma ação por problema, sem repetir.\n"
    "- manter: o que já está certo e não pode ser perdido na reescrita (fatos e números já presentes, termos já "
    "explicados, limites de tamanho que já foram respeitados).\n"
    "- Acrescentar fatos costuma piorar a legibilidade e trazer termos técnicos de volta: quando uma ação pedir para incluir "
    "fato ou número, diga também como mantê-lo no nível (iniciante: uma frase curta só para ele, sem jargão; intermediário e "
    "avançado: frases do tamanho do nível). Termo proibido ou sem explicação vale também para as variantes dele.\n"
    "- Se a falha for a analogia exigida no iniciante, localize TODOS os termos técnicos do texto e escreva, para cada um, a "
    "analogia pronta do dia a dia no molde 'X é como ...' (sem número novo), dizendo em que frase ela entra; basta um termo "
    "sem analogia para o texto ser reprovado.\n"
    "- Se a falha for um item da rubrica do nível (alocação e tendências no intermediário, o que muda no bolso no iniciante, "
    "implicação analítica no avançado), escreva a frase pronta que atende o item, sem número novo, e diga onde ela entra; em "
    "carrossel, diga qual slide sai ou encurta para abrir espaço sem passar do limite de caracteres.\n"
    "- Nunca proponha número, fato ou nome que não esteja nos fatos fornecidos. Nunca proponha recomendar compra, venda ou "
    "aplicação. Corrija um problema sem criar outro: se a ação aumenta o texto, diga o que cortar para continuar dentro "
    "do limite."
)


def _explicacoes(falhas: list[str], termos: list[Termo]) -> str:
    """Explicação pronta dos termos citados nas falhas, para o plano poder dizer exatamente o que escrever."""
    citados = {m.lower() for f in falhas for m in re.findall(r"'([^']+)'", f)}
    achados = [t for t in termos if t.explicacao and t.termo.lower() in citados]
    return "\n".join(f"- {t.termo}: {t.explicacao}" for t in achados[:10])


def montar_pedido(nivel: str, formato: str, ancora: Ancora, texto: str, falhas: list[str], termos: list[Termo]) -> str:
    fatos = "\n".join(f"[{f.id}] {f.texto}" + (f" (números: {', '.join(f.numeros)})" if f.numeros else "") for f in ancora.fatos)
    itens = "\n".join(f"- {x}" for x in falhas)
    explic = _explicacoes(falhas, termos)
    bloco_termos = f"\nEXPLICAÇÕES PRONTAS DOS TERMOS CITADOS:\n{explic}\n" if explic else ""
    return (f"NÍVEL: {nivel}. FORMATO: {formato}.\n\nFATOS PERMITIDOS:\n{fatos}\n\nFALHAS DO AVALIADOR:\n{itens}\n"
            f"{bloco_termos}\nVERSÃO REPROVADA:\n{texto}")


def planejar(cliente: Cliente, nivel: str, formato: str, ancora: Ancora, texto: str, falhas: list[str],
             termos: list[Termo]) -> PlanoLLM:
    bruto = cliente.completar_json(SISTEMA, montar_pedido(nivel, formato, ancora, texto, falhas, termos), schema_plano(PlanoLLM))
    plano = PlanoLLM.model_validate(bruto)
    plano.acoes = [a.strip() for a in plano.acoes if a.strip()][:6]
    plano.manter = [m.strip() for m in plano.manter if m.strip()][:6]
    return plano


def plano_em_texto(plano: PlanoLLM) -> str:
    """Bloco que entra no prompt do gerador, depois do relatório de falhas."""
    linhas = ["PLANO DO REVISOR PARA ESTA REESCRITA (siga na ordem):", f"Diagnóstico: {plano.diagnostico.strip()}"]
    linhas += [f"{i}. {a}" for i, a in enumerate(plano.acoes, 1)]
    if plano.manter:
        linhas += ["MANTENHA:"] + [f"- {m}" for m in plano.manter]
    return "\n".join(linhas)
