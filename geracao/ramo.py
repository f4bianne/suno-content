"""Um ramo do grafo (um nível x um formato): gerar, avaliar e, se reprovar, refazer com o relatório (itens 18 e 19).

Padrão de reflexão: o avaliador devolve falhas numéricas, elas entram no prompt da próxima tentativa, e o ramo
termina aprovado ou bloqueado depois de `max_tentativas`. Cada tentativa fica registrada.
"""
import re
import time
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from avaliador import avaliar as av
from avaliador import formatos, glossario
from avaliador.ancora import Ancora
from avaliador.juiz import Cliente, julgar, schema_plano
from geracao import prompts, schemas


class Tentativa(BaseModel):
    n: int
    aprovado: bool
    falhas: list[str]
    metricas: dict[str, Any] = {}
    veredito: dict[str, Any] | None = None
    conteudo: dict[str, Any] | None = None
    segundos_geracao: float = 0.0
    segundos_avaliacao: float = 0.0
    chamadas_llm: int = 0


class ResultadoRamo(BaseModel):
    nivel: str
    formato: str
    status: str                       # "aprovado" ou "bloqueado"
    conteudo: dict[str, Any] | None
    tentativas: list[Tentativa]


class EstadoRamo(TypedDict, total=False):
    nivel: str
    formato: str
    ancora: Ancora
    tentativa: int
    conteudo: Any
    erro_geracao: str | None
    segundos_geracao: float
    feedback: str | None
    status: str
    tentativas: list[Tentativa]
    juiz_indisponivel: int


def _dica(f: av.Falha, ancora: Ancora, metricas: dict, indice: glossario.Indice | None = None) -> str:
    """Mensagem da falha acrescida de uma orientação acionável."""
    extra = ""
    if f.metrica == "legibilidade":
        faixa = re.search(r"faixa (\d+) a (\d+)", f.mensagem)
        if faixa:
            lo, hi = int(faixa[1]), int(faixa[2])
            sentido = ("Reescreva com frases mais curtas e palavras mais simples." if metricas.get("flesch", 0) < lo
                       else "Use frases mais longas e vocabulário mais técnico.")
            extra = f" {sentido} Mire no meio da faixa (cerca de {(lo + hi) // 2}) com um ajuste moderado, sem exagerar."
    elif f.metrica == "cobertura":
        por_id = {x.id: x.texto for x in ancora.fatos}
        faltou = "; ".join(f"[{i}] {por_id.get(i, '')}" for i in metricas.get("fatos_ausentes", []))
        extra = (f" Inclua estes fatos com seus números, um por frase (ou cena), e mantenha o que já estava certo: {faltou}."
                 if faltou else "")
    elif f.metrica == "formato":
        extra = " Respeite os limites do formato: corte o que for menos importante em vez de comprimir o texto."
    elif f.metrica == "numeros":
        validos = sorted({n for x in ancora.fatos for n in x.numeros})
        extra = (" Remova ou corrija: só valem números que estão nos fatos."
                 + (f" Os únicos números permitidos são: {', '.join(validos)}. Não calcule, não some e não converta." if validos else ""))
    elif f.metrica == "glossario":
        extra = " Troque o termo por palavras simples ou explique-o na mesma frase (\"ou seja\", \"que é\")."
        nome = re.search(r"'([^']+)'", f.mensagem)
        achado = None
        if indice is not None and nome:
            achado = next((t for t in indice.termos if t.termo.lower() == nome[1].lower() and t.explicacao), None)
        if achado:
            extra += f" Na primeira vez em que usar \"{achado.termo}\", escreva algo como: {achado.termo}, que é {achado.explicacao}."
    elif f.metrica == "recomendacao":
        extra = " Descreva o fato sem aconselhar compra, venda ou aplicação."
    return f"[{f.metrica}] {f.mensagem}.{extra}"


def _falhas_do_juiz(v) -> list[str]:
    itens = [f"[juiz] afirmação sem suporte nos fatos (remova ou reescreva): {a}" for a in v.afirmacoes_sem_suporte]
    itens += [f"[juiz] critério do nível não atendido: {c}" for c in v.criterios_nao_atendidos]
    itens += [f"[juiz] fato ausente: {i}" for i in v.fatos_ausentes]
    if not itens and not v.aprovado:
        itens.append(f"[juiz] notas baixas (fidelidade {v.nota_fidelidade}, nível {v.nota_adequacao_nivel}): {v.justificativa}")
    return itens


def construir_ramo(gerador: Cliente, juiz: Cliente, indice: glossario.Indice, cfg: dict, max_tentativas: int = 3,
                   tentativas_juiz: int = 3, espera_juiz_s: float = 20.0, observador: Callable[[dict], None] | None = None):
    termos = indice.termos

    def avisar(evento: dict) -> None:
        if observador:
            observador(evento)

    def no_gerar(e: EstadoRamo) -> EstadoRamo:
        n = e.get("tentativa", 0) + 1
        avisar({"tipo": "gerando", "nivel": e["nivel"], "formato": e["formato"], "tentativa": len(e.get("tentativas", [])) + 1})
        t0 = time.time()
        try:
            bruto = gerador.completar_json(
                prompts.sistema(e["nivel"], e["formato"], termos, cfg),
                prompts.usuario(e["ancora"], e.get("feedback")),
                schema_plano(schemas.SCHEMA_POR_FORMATO[e["formato"]]),
            )
            conteudo, erro = schemas.para_conteudo(e["formato"], bruto), None
        except Exception as ex:   # JSON fora do schema, falha de rede depois dos retries etc.
            conteudo, erro = None, f"{type(ex).__name__}: {str(ex)[:200]}"
        return {"tentativa": n, "conteudo": conteudo, "erro_geracao": erro, "segundos_geracao": time.time() - t0}

    def no_avaliar(e: EstadoRamo) -> EstadoRamo:
        t0, conteudo, indisponivel = time.time(), e["conteudo"], False
        tent = Tentativa(n=len(e.get("tentativas", [])) + 1, aprovado=False, falhas=[], segundos_geracao=round(e["segundos_geracao"], 2),
                         chamadas_llm=1)
        if conteudo is None:
            tent.falhas = [f"[formato] a resposta não obedeceu ao formato pedido ({e['erro_geracao']}). Responda no schema."]
        else:
            tent.conteudo = schemas.conteudo_em_dict(conteudo)
            res = av.avaliar(conteudo, e["nivel"], indice, e["ancora"], cfg)
            tent.metricas = res.metricas
            tent.falhas = [_dica(f, e["ancora"], res.metricas, indice) for f in res.falhas]
            if res.aprovado:   # o juiz só roda depois das regras: poupa chamadas e as regras já dão o feedback
                for volta in range(tentativas_juiz):   # limite de uso passa com um pouco de espera
                    try:
                        v = julgar(juiz, formatos.texto_corrido(conteudo), e["nivel"], e["formato"], e["ancora"], res.indeterminados)
                        tent.chamadas_llm += 1
                        tent.veredito = v.model_dump()
                        tent.falhas = _falhas_do_juiz(v)
                        indisponivel = False
                        break
                    except Exception as ex:
                        resp = getattr(ex, "response", None)
                        detalhe = f"HTTP {resp.status_code}: {resp.text[:120]}" if resp is not None else type(ex).__name__
                        tent.falhas = [f"[juiz] não foi possível avaliar ({detalhe})"]
                        indisponivel = True
                        if resp is not None and resp.status_code == 400:
                            break   # saída fora do schema: esperar não adianta, e o limite de uso não é o problema
                        if volta < tentativas_juiz - 1:
                            time.sleep(espera_juiz_s)
        tent.aprovado = not tent.falhas
        tent.segundos_avaliacao = round(time.time() - t0, 2)
        avisar({"tipo": "avaliado", "nivel": e["nivel"], "formato": e["formato"], "tentativa": tent.n, "aprovado": tent.aprovado,
                "falhas": [x.split("]")[0] + "]" for x in tent.falhas], "flesch": tent.metricas.get("flesch")})
        feedback = None
        if not tent.aprovado:
            feedback = (prompts.relatorio_de_falhas(tent.falhas, conteudo) if conteudo is not None
                        else "A tentativa anterior falhou: " + "; ".join(tent.falhas))
        saida = {"tentativas": [*e.get("tentativas", []), tent], "feedback": feedback,
                 "status": "aprovado" if tent.aprovado else "reprovado"}
        # Juiz fora do ar (limite de uso, rede) não é culpa do texto: não gasta a tentativa, até 2 vezes por ramo.
        if indisponivel and e.get("juiz_indisponivel", 0) < 2:
            saida["tentativa"] = e["tentativa"] - 1
            saida["juiz_indisponivel"] = e.get("juiz_indisponivel", 0) + 1
        return saida

    def decidir(e: EstadoRamo) -> str:
        if e["status"] == "aprovado":
            return "fim"
        return "bloquear" if e["tentativa"] >= max_tentativas else "refazer"

    def no_bloquear(e: EstadoRamo) -> EstadoRamo:
        return {"status": "bloqueado"}

    g = StateGraph(EstadoRamo)
    g.add_node("gerar", no_gerar)
    g.add_node("avaliar", no_avaliar)
    g.add_node("bloquear", no_bloquear)
    g.add_edge(START, "gerar")
    g.add_edge("gerar", "avaliar")
    g.add_conditional_edges("avaliar", decidir, {"fim": END, "refazer": "gerar", "bloquear": "bloquear"})
    g.add_edge("bloquear", END)
    return g.compile()


def rodar_ramo(ramo, nivel: str, formato: str, ancora: Ancora, max_fatos: int | None = None) -> ResultadoRamo:
    """`max_fatos` limita a âncora ao que cabe no formato (vídeo de 60 s não comporta 12 fatos)."""
    if max_fatos is not None:
        ancora = Ancora(fatos=ancora.fatos[:max_fatos])
    final = ramo.invoke({"nivel": nivel, "formato": formato, "ancora": ancora, "tentativa": 0, "tentativas": [], "feedback": None})
    ultima = final["tentativas"][-1]
    return ResultadoRamo(nivel=nivel, formato=formato, status=final["status"], conteudo=ultima.conteudo,
                         tentativas=final["tentativas"])
