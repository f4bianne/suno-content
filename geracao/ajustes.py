"""Ajuste determinístico antes da avaliação: explica, com a definição do glossário, o termo que veio sem explicação.

Com só duas tentativas (a original e uma de ajuste), cada reprovação evitável pesa. Termo técnico sem explicação é o
tipo de falha que não precisa de modelo para ser consertado: a definição já está no glossário e o ponto de inserção é
exato. O texto ajustado é o mesmo que o avaliador mede e que a pessoa lê. Termo proibido no nível (por exemplo,
nível 3 no iniciante) NÃO é mexido: trocar a palavra à mão quebraria a gramática, e isso fica com o gerador.
"""
from avaliador import formatos
from avaliador.formatos import Artigo, Carrossel, Conteudo, Roteiro
from avaliador.glossario import Indice, _limites_sentencas, explicado

JANELA = 250     # o avaliador perdoa uma menção sem explicação se a explicação vem logo depois, nesta distância


def _inserir_explicacoes(texto: str, indice: Indice, minimo: int, maximo: int, ja: set[str], limite: int | None
                         ) -> tuple[str, list[str]]:
    """Insere ', que é <definição>' depois da primeira menção sem explicação de cada termo que a exige."""
    ocorrencias = indice.encontrar(texto)
    limites = _limites_sentencas(texto)
    explicadas_em: dict[str, list[int]] = {}
    for o in ocorrencias:
        if explicado(o, texto, limites):
            explicadas_em.setdefault(o.termo.termo, []).append(o.inicio)
    pontos: list[tuple[int, str]] = []
    feitos: list[str] = []
    for o in ocorrencias:
        t = o.termo
        if not minimo < t.nivel <= maximo or not t.explicacao or t.termo in ja:
            continue
        if explicado(o, texto, limites):
            ja.add(t.termo)
        elif any(0 < p - o.fim <= JANELA for p in explicadas_em.get(t.termo, [])):
            ja.add(t.termo)          # a explicação vem logo depois: o avaliador aceita
        else:
            seguinte = texto[o.fim:o.fim + 1]
            fecha = "" if seguinte == "" or seguinte in ".,;:!?)-–—" else ","     # no meio da frase, a explicação fecha com vírgula
            pontos.append((o.fim, f", que é {t.explicacao}{fecha}"))
            ja.add(t.termo)
            feitos.append(t.termo)
    novo = texto
    for pos, trecho in sorted(pontos, reverse=True):          # de trás para frente, para não deslocar as posições
        novo = novo[:pos] + trecho + novo[pos:]
    if limite is not None and len(novo) > limite and novo != texto:
        return texto, []                                      # estouraria o limite do slide: deixa como está
    return novo, feitos


def explicar_termos(conteudo: Conteudo, nivel: str, indice: Indice, cfg: dict) -> tuple[Conteudo, list[str]]:
    """Devolve o conteúdo com os termos explicados e a lista dos termos em que houve inserção."""
    regras = cfg["niveis"][nivel]
    minimo, maximo = regras["nivel_maximo_termo_sem_explicacao"], regras["nivel_maximo_termo_com_explicacao"]
    if minimo >= maximo:                                      # avançado: nada exige explicação
        return conteudo, []
    ja: set[str] = set()
    todos: list[str] = []

    def ajustar(texto: str, limite: int | None = None) -> str:
        novo, feitos = _inserir_explicacoes(texto, indice, minimo, maximo, ja, limite)
        todos.extend(feitos)
        return novo

    if isinstance(conteudo, Artigo):
        novo: Conteudo = Artigo(titulo=ajustar(conteudo.titulo), corpo=ajustar(conteudo.corpo), conclusao=ajustar(conteudo.conclusao))
    elif isinstance(conteudo, Carrossel):
        c = cfg["formatos"]["carrossel"]
        com_grafico = {g.slide for g in conteudo.graficos}     # o texto desses slides divide o espaço com o gráfico
        limite = lambda i: c.get("grafico", {}).get("caracteres_no_slide", 120) if i in com_grafico else c["caracteres_por_slide"]
        novo = conteudo.model_copy(update={"slides": [ajustar(s, limite(i)) for i, s in enumerate(conteudo.slides)]})
    elif isinstance(conteudo, Roteiro):
        from geracao.schemas import marcar_tempo          # a fala cresceu: o tempo das cenas acompanha
        falas = [{"fala": ajustar(c.fala), "visual": c.visual} for c in conteudo.cenas]
        novo = Roteiro(cenas=marcar_tempo(falas))
    else:
        return conteudo, []
    assert formatos.formato_de(novo) == formatos.formato_de(conteudo)
    return novo, todos
