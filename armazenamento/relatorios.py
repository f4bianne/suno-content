"""Experimentos sobre o que esta no banco (itens 23 e 24): matriz de confusao, convergencia, custo e latencia.

Tudo e calculado a partir das execucoes guardadas; nenhuma chamada a modelo e necessaria, exceto o classificador
por LLM, que e opcional. O "antes do loop" e a PRIMEIRA tentativa de cada ramo; o "depois" e a ultima.
"""
from dataclasses import dataclass, field
from statistics import mean

from sqlalchemy import select

from avaliador import classificador, glossario
from avaliador.formatos import Artigo, Carrossel, Roteiro, texto_corrido
from armazenamento.repositorio import Repositorio, documentos, execucoes, ramos, tentativas

NIVEIS = classificador.NIVEIS
FORMATOS = ("artigo", "carrossel", "video")


@dataclass
class RamoRegistro:
    execucao_id: str
    origem: str
    nivel: str
    formato: str
    status: str
    tentativas: list[dict] = field(default_factory=list)
    conteudo_final: dict | None = None

    @property
    def primeiro_conteudo(self) -> dict | None:
        for t in self.tentativas:
            if t["conteudo"]:
                return t["conteudo"]
        return None

    @property
    def aprovou_na_primeira(self) -> bool:
        return bool(self.tentativas) and self.tentativas[0]["aprovado"]

    @property
    def chamadas(self) -> int:
        return sum(t["chamadas_llm"] for t in self.tentativas)

    @property
    def segundos(self) -> float:
        return sum(t["segundos_geracao"] + t["segundos_avaliacao"] for t in self.tentativas)


def carregar(repo: Repositorio, execucao_ids: list[str] | None = None) -> list[RamoRegistro]:
    """Todos os ramos guardados (ou so os das execucoes pedidas), com suas tentativas."""
    saida: list[RamoRegistro] = []
    with repo.engine.connect() as c:
        q = (select(ramos, documentos.c.origem).join(execucoes, execucoes.c.id == ramos.c.execucao_id)
             .join(documentos, documentos.c.id == execucoes.c.documento_id).order_by(execucoes.c.criado_em, ramos.c.id))
        if execucao_ids:
            q = q.where(ramos.c.execucao_id.in_(execucao_ids))
        for r in c.execute(q).mappings():
            ts = c.execute(select(tentativas).where(tentativas.c.ramo_id == r["id"]).order_by(tentativas.c.n, tentativas.c.id)).mappings().all()
            saida.append(RamoRegistro(r["execucao_id"], r["origem"], r["nivel"], r["formato"], r["status"],
                                      [dict(t) for t in ts], r["conteudo"]))
    return saida


def texto_do_conteudo(formato: str, c: dict) -> str:
    """Texto que o leitor recebe, o mesmo que o avaliador mede."""
    if formato == "artigo":
        return texto_corrido(Artigo(**c))
    if formato == "carrossel":
        return texto_corrido(Carrossel(**c))
    return texto_corrido(Roteiro(**c))


class ClienteComCache:
    """Guarda a resposta por texto: o mesmo texto aparece em varias tabelas e so deve ser classificado uma vez."""

    def __init__(self, cliente):
        self.cliente, self.memo, self.chamadas = cliente, {}, 0

    def completar_json(self, sistema: str, usuario: str, schema: dict) -> dict:
        chave = (sistema, usuario)
        if chave not in self.memo:
            self.chamadas += 1
            self.memo[chave] = self.cliente.completar_json(sistema, usuario, schema)
        return self.memo[chave]


def _conteudo_no_momento(r: RamoRegistro, momento: str) -> dict | None:
    return r.primeiro_conteudo if momento == "antes" else r.conteudo_final


def matriz(registros: list[RamoRegistro], momento: str, indice: glossario.Indice, formato: str | None = None,
           so_aprovados: bool = False, cliente_llm=None) -> dict:
    """Matriz de confusao do classificador cego. `momento` = "antes" (1a tentativa) ou "depois" (versao final)."""
    reais, previstos, n_sem_conteudo = [], [], 0
    for r in registros:
        if (formato and r.formato != formato) or (so_aprovados and r.status != "aprovado"):
            continue
        c = _conteudo_no_momento(r, momento)
        if not c:
            n_sem_conteudo += 1
            continue
        texto = texto_do_conteudo(r.formato, c)
        reais.append(r.nivel)
        previstos.append(classificador.classificar_por_llm(cliente_llm, texto) if cliente_llm
                         else classificador.classificar_por_regras(texto, indice))
    m = classificador.matriz_confusao(reais, previstos)
    return {"matriz": m, "n": len(reais), "acuracia": classificador.acuracia(m) if reais else None, "sem_conteudo": n_sem_conteudo}


def flesch_por_nivel(registros: list[RamoRegistro], momento: str = "depois") -> dict[str, float]:
    """Flesch medio da versao final (ou da 1a tentativa) por nivel: mostra se os niveis se separam na leitura."""
    por: dict[str, list[float]] = {n: [] for n in NIVEIS}
    for r in registros:
        t = (r.tentativas[0] if momento == "antes" else r.tentativas[-1]) if r.tentativas else None
        if t and t["metricas"].get("flesch") is not None:
            por[r.nivel].append(t["metricas"]["flesch"])
    return {n: round(mean(v), 1) for n, v in por.items() if v}


def _linha(grupo: list[RamoRegistro]) -> dict:
    n = len(grupo)
    aprovados = [r for r in grupo if r.status == "aprovado"]
    return {
        "ramos": n,
        "aprovados": len(aprovados),
        "taxa_aprovacao": len(aprovados) / n if n else 0.0,
        "aprovou_na_primeira": sum(r.aprovou_na_primeira for r in grupo) / n if n else 0.0,
        "recuperados_pelo_loop": sum(1 for r in aprovados if not r.aprovou_na_primeira),
        "tentativas_media": mean(len(r.tentativas) for r in grupo) if n else 0.0,
        "chamadas_media": mean(r.chamadas for r in grupo) if n else 0.0,
        "segundos_media": mean(r.segundos for r in grupo) if n else 0.0,
    }


def convergencia_e_custo(registros: list[RamoRegistro]) -> dict:
    """Aprovacao, tentativas, chamadas e segundos, no total e por nivel e por formato."""
    return {
        "total": _linha(registros),
        "por_nivel": {n: _linha([r for r in registros if r.nivel == n]) for n in NIVEIS if any(r.nivel == n for r in registros)},
        "por_formato": {f: _linha([r for r in registros if r.formato == f]) for f in FORMATOS if any(r.formato == f for r in registros)},
    }


def execucoes_resumo(repo: Repositorio) -> dict:
    """Tempo de parede por execucao e taxa de acerto do cache."""
    with repo.engine.connect() as c:
        segs = [s for (s,) in c.execute(select(execucoes.c.segundos))]
    acertos, total = repo.taxa_de_cache()
    return {"execucoes": len(segs), "segundos_media": mean(segs) if segs else 0.0, "segundos_max": max(segs) if segs else 0.0,
            "acessos": total, "acertos_de_cache": acertos}


# ---------- texto ----------

def _fmt_matriz(m: dict) -> list[str]:
    if m["n"] == 0:
        return ["(sem dados)"]
    linhas = [f"| real \\ previsto | {' | '.join(NIVEIS)} |", "|---|" + "---|" * len(NIVEIS)]
    for r in NIVEIS:
        linhas.append(f"| **{r}** | " + " | ".join(str(m["matriz"][r][p]) for p in NIVEIS) + " |")
    linhas.append(f"\nAcuracia: **{m['acuracia']:.0%}** em {m['n']} textos" + (f" ({m['sem_conteudo']} ramos sem texto foram ignorados)" if m["sem_conteudo"] else ""))
    return linhas


def _fmt_tabela_custo(grupos: dict[str, dict], rotulo: str) -> list[str]:
    linhas = [f"| {rotulo} | ramos | aprovados | aprovou na 1a | recuperados pelo loop | tentativas (media) | chamadas (media) | segundos (media) |",
              "|---|---|---|---|---|---|---|---|"]
    for nome, g in grupos.items():
        linhas.append(f"| {nome} | {g['ramos']} | {g['aprovados']} ({g['taxa_aprovacao']:.0%}) | {g['aprovou_na_primeira']:.0%} | "
                      f"{g['recuperados_pelo_loop']} | {g['tentativas_media']:.1f} | {g['chamadas_media']:.1f} | {g['segundos_media']:.0f} |")
    return linhas


def relatorio_markdown(repo: Repositorio, indice: glossario.Indice, execucao_ids: list[str] | None = None, cliente_llm=None) -> str:
    regs = carregar(repo, execucao_ids)
    if not regs:
        return "Nenhuma execucao no banco."
    nome_clf = "LLM (classificador cego)" if cliente_llm else "regras (glossario + legibilidade)"
    docs = sorted({r.origem for r in regs})
    exec_n = len({r.execucao_id for r in regs})
    out = [f"# Resultados dos experimentos", "",
           f"Base: **{exec_n} execucoes**, **{len(regs)} ramos** (nivel x formato), {len(docs)} documento(s): {', '.join(docs)}.", "",
           "## 1. Matriz de confusao dos niveis", "",
           f"Classificador: {nome_clf}. Ele recebe so o texto, nunca o nivel-alvo. "
           "Se acerta, o texto gerado para aquele nivel e reconhecivel como tal.", ""]
    if not cliente_llm:
        out += ["> **Limite:** o classificador por regras usa o mesmo glossario e a mesma legibilidade que o avaliador aplica. "
                "Por isso a acuracia depois do loop (e entre os ramos aprovados) tende a ser alta quase por construcao. "
                "A medida independente e a do classificador por LLM (`relatorio --llm`), que le o texto sem conhecer as regras.", ""]
    for momento, titulo in (("antes", "Antes do loop (primeira tentativa de cada ramo)"), ("depois", "Depois do loop (versao final de cada ramo)")):
        out += [f"### {titulo}", ""] + _fmt_matriz(matriz(regs, momento, indice, cliente_llm=cliente_llm)) + [""]
    out += ["### Por formato (versao final)", ""]
    for f in FORMATOS:
        m = matriz(regs, "depois", indice, formato=f, cliente_llm=cliente_llm)
        out += [f"**{f}**: " + (f"{m['acuracia']:.0%} em {m['n']} textos" if m["n"] else "sem dados")]
    out += ["", "### Somente os ramos aprovados (versao final)", ""] + _fmt_matriz(
        matriz(regs, "depois", indice, so_aprovados=True, cliente_llm=cliente_llm)) + [""]
    fl = flesch_por_nivel(regs)
    if fl:
        out += ["### Flesch medio da versao final, por nivel", "",
                " · ".join(f"{n}: **{v}**" for n, v in fl.items()), "",
                "Se os niveis estao bem separados, o numero cai de iniciante para avancado.", ""]
    cc = convergencia_e_custo(regs)
    out += ["## 2. Convergencia, custo e latencia", "",
            "Tentativas, chamadas e segundos sao somados por ramo (os ramos rodam em paralelo; o tempo real de uma execucao e menor).", ""]
    out += _fmt_tabela_custo({"**total**": cc["total"]}, "grupo") + [""]
    out += _fmt_tabela_custo({ROT: g for ROT, g in cc["por_nivel"].items()}, "nivel") + [""]
    out += _fmt_tabela_custo({ROT: g for ROT, g in cc["por_formato"].items()}, "formato") + [""]
    ex = execucoes_resumo(repo)
    taxa = f"{ex['acertos_de_cache'] / ex['acessos']:.0%} ({ex['acertos_de_cache']} de {ex['acessos']} pedidos)" if ex["acessos"] else "sem pedidos registrados ainda"
    out += ["## 3. Cache e tempo por execucao", "",
            f"- Execucoes guardadas: {ex['execucoes']}; tempo de parede medio **{ex['segundos_media']:.0f} s** (maximo {ex['segundos_max']:.0f} s).",
            f"- Taxa de acerto do cache: {taxa}.",
            "- Um pedido que acerta o cache leva cerca de 1 s e nao chama nenhum modelo.", ""]
    return "\n".join(out)
