"""Prompts do gerador: perfil do nível, instruções do formato e relatório de falhas para a nova tentativa."""
from avaliador import glossario
from avaliador.ancora import Ancora
from avaliador.formatos import Conteudo, texto_corrido
from avaliador.glossario import Termo

PERFIL = {
    "iniciante": (
        "leitores iniciantes. Zero jargão financeiro sem analogia do dia a dia. Frases curtas (até 15 palavras) e palavras "
        "simples. Foco no impacto prático no bolso de quem lê (parcela, preço, rendimento da poupança, dívida). OBRIGATÓRIO: "
        "(1) traduza o conceito principal com uma analogia do dia a dia (feira, conta de casa, empréstimo entre amigos) e "
        "(2) inclua uma frase que diga o que muda no bolso de quem lê, como consequência geral e sem números novos."
    ),
    "intermediario": (
        "leitores intermediários, que conhecem o vocabulário de mercado padrão (CDI, Selic, IPCA, dividendos) e não precisam "
        "de didatismo infantil. Frases de 20 a 30 palavras, com vocabulário de mercado. Foco em alocação e tendências. "
        "Termos mais técnicos só com uma explicação curta. OBRIGATÓRIO: inclua uma frase que relacione os dados a alocação e "
        "tendências (o que os dados sugerem para renda fixa, renda variável ou câmbio), sem recomendar compra ou venda."
    ),
    "avancado": (
        "profissionais do mercado. Preserve o jargão pleno do documento e sua nuance metodológica; não simplifique nem "
        "infantilize. Frases longas e densas (25 a 40 palavras) com vocabulário técnico. Foco analítico e metodológico. "
        "Explicite implicações que o documento só sugere, sem inventar."
    ),
}


def _nomes(termos: list[Termo], nivel: int, limite: int | None = None) -> str:
    nomes = sorted({t.termo for t in termos if t.nivel == nivel and not t.ambiguo})
    return ", ".join(nomes[:limite] if limite else nomes)


def regra_de_termos(nivel: str, termos: list[Termo]) -> str:
    if nivel == "iniciante":
        return (
            f"TERMOS PROIBIDOS (nem explicados): {_nomes(termos, 3)}.\n"
            f"TERMOS QUE EXIGEM EXPLICAÇÃO na mesma frase ou na seguinte, com analogia: {_nomes(termos, 2, 80)}. "
            "Escreva a explicação com marcadores como \"ou seja\", \"que é\" ou \"chamada\"."
        )
    if nivel == "intermediario":
        return (
            f"TERMOS QUE EXIGEM EXPLICAÇÃO curta (\"ou seja\", \"que é\") na mesma frase ou na seguinte: {_nomes(termos, 3)}. "
            "Os termos de mercado padrão podem aparecer livremente."
        )
    return (
        "Todos os termos são permitidos. Use os termos técnicos do documento; o texto deve ter densidade de termos de "
        f"mercado (exemplos: {_nomes(termos, 3, 25)})."
    )


_INDICES: dict[int, glossario.Indice] = {}


def termos_do_documento(nivel: str, termos: list[Termo], ancora: Ancora | None) -> str:
    """Termos do glossário que aparecem nos fatos deste documento, cada um com a explicação pronta.

    É o que mais reprova no nível iniciante: o termo aparece e a explicação fica para depois. Aqui o gerador já recebe
    a forma exata de escrevê-lo na primeira vez (o avaliador aceita ", que é ..." logo depois do termo)."""
    if ancora is None or nivel == "avancado":
        return ""
    indice = _INDICES.setdefault(id(termos), glossario.Indice(termos))
    fonte = "\n".join(f"{f.texto} {f.trecho_origem}" for f in ancora.fatos)
    minimo = 2 if nivel == "iniciante" else 3     # a partir de que nível o termo precisa de explicação
    vistos: dict[str, Termo] = {}
    for oc in indice.encontrar(fonte):
        if oc.termo.nivel >= minimo and oc.termo.explicacao and oc.termo.termo not in vistos:
            vistos[oc.termo.termo] = oc.termo
    if not vistos:
        return ""
    linhas = []
    for t in list(vistos.values())[:15]:
        if nivel == "iniciante" and t.nivel >= 3:
            linhas.append(f"- {t.termo} (proibido): troque por palavras simples, como \"{t.explicacao}\".")
        else:
            linhas.append(f"- {t.termo}, que é {t.explicacao}")
    return (
        "TERMOS DESTE DOCUMENTO, COM A EXPLICAÇÃO PRONTA. A PRIMEIRA vez que um deles aparece, em qualquer parte do texto "
        "(inclusive título, gancho e fala), escreva-o já com a explicação, exatamente neste molde; depois pode usar só o "
        "nome:\n" + "\n".join(linhas) + "\n"
    )


def instrucao_formato(formato: str, cfg: dict) -> str:
    f = cfg["formatos"]
    if formato == "artigo":
        lo, hi = f["artigo"]["palavras"]
        # Os modelos costumam escrever menos do que o pedido: mirar acima do mínimo é o que faz o texto passar dele.
        return (f"FORMATO: artigo analítico para web ou newsletter, com título, corpo e conclusão. REGRA DURA: entre {lo + 150} e "
                f"{hi - 250} palavras no total (menos de {lo} é rejeitado, e você tende a escrever menos do que mira: mire "
                f"alto). ESTRUTURA: corpo de 4 a 5 parágrafos de 80 a 100 palavras, cada um com um fato, o contexto dele e o que "
                "significa para quem lê; conclusão de uns 60 palavras em um parágrafo novo, sem repetir o corpo. Desenvolva com "
                "contexto e consequências gerais, sem número ou dado novo e sem enrolação.")
    if formato == "carrossel":
        lo, hi = f["carrossel"]["slides"]
        c = f["carrossel"]["caracteres_por_slide"]
        return (f"FORMATO: carrossel. gancho (slide 1, que prende a atenção), slides_corpo (de {lo - 2} a {hi - 2} slides) e "
                f"conclusao (último slide). O total, contando gancho e conclusão, fica entre {lo} e {hi} slides. REGRA DURA: "
                f"cada slide tem no máximo {c - 30} caracteres (conte; slide acima de {c} é rejeitado). Cada slide de corpo "
                "traz uma ideia completa. Não cabe tudo: priorize os fatos mais importantes.")
    pmax, pps = f["video"]["duracao_maxima_s"], f["video"]["palavras_por_segundo"]
    minimo, limite = int((pmax - 12) * pps), int((pmax - 4) * pps)     # 120 a 140 palavras: de 48 a 56 s de fala
    return (f"FORMATO: roteiro de vídeo curto, falado, que ocupa quase todo o tempo de {pmax} segundos. Cada cena tem: "
            "fala (a narração lida em voz alta) e visual (a ação e as imagens: o que a pessoa faz e o que aparece, em uma "
            "frase concreta, como \"mãos segurando uma nota de cem reais\"). Não escreva marcação de tempo: ela é calculada "
            "a partir do tamanho de cada fala. "
            f"REGRA DURA: some todas as falas e escreva entre {minimo} e {limite} palavras (de {int(minimo / pps)} a "
            f"{int(limite / pps)} segundos de fala). Abaixo de {minimo} o vídeo fica curto e deixa fatos de fora; acima de "
            f"{int(pmax * pps)} passa de {pmax} s e é rejeitado. Cada fala tem de 15 a 30 palavras: frases completas, com "
            "contexto, e não só o dado solto. "
            "ESTRUTURA, de 5 a 7 cenas: (1) gancho que prende em poucos segundos; (2) o contexto, o que aconteceu; (3) uma cena "
            "para CADA fato fornecido, com o número dito na fala exatamente como está nos fatos e uma frase sobre o que ele "
            "quer dizer; (4) o que isso muda ou significa para quem assiste, como consequência geral e sem número novo; "
            "(5) fechamento que resume a ideia, sem pedir para comprar, vender ou aplicar nada. "
            "Termo técnico que exige explicação é explicado na própria cena.")


def sistema(nivel: str, formato: str, termos: list[Termo], cfg: dict, ancora: Ancora | None = None) -> str:
    return (
        "Você adapta documentos financeiros oficiais brasileiros, em português do Brasil, para um público e um formato.\n"
        f"PÚBLICO: {PERFIL[nivel]}\n{regra_de_termos(nivel, termos)}\n{termos_do_documento(nivel, termos, ancora)}"
        f"{instrucao_formato(formato, cfg)}\n"
        "REGRAS DE FIDELIDADE:\n"
        "- Use SOMENTE os fatos fornecidos. Todo número citado deve existir nos fatos, escrito igual (não calcule nem arredonde).\n"
        "- Cubra todos os fatos. Se dois forem parecidos, junte-os numa frase mantendo todos os números.\n"
        "- Consequências econômicas gerais (por exemplo, juros altos encarecem o crédito) são permitidas, sem números novos.\n"
        "- Não dê conselho de compra, venda ou aplicação; não use imperativos de investimento.\n"
        "- Não invente datas, nomes, decisões ou previsões."
    )


def fatos_em_texto(ancora: Ancora) -> str:
    return "\n".join(f"[{f.id}] {f.texto}" + (f" (números: {', '.join(f.numeros)})" if f.numeros else "") for f in ancora.fatos)


def relatorio_de_falhas(falhas: list[str], anterior: Conteudo) -> str:
    itens = "\n".join(f"- {x}" for x in falhas)
    return (
        "A VERSÃO ANTERIOR FOI REPROVADA PELO AVALIADOR. Corrija TODOS os problemas abaixo e reescreva por inteiro. "
        "Mantenha o que já estava certo (fatos, números e termos já aprovados) e mude só o necessário: corrigir um "
        "problema não pode criar outro.\n"
        f"PROBLEMAS:\n{itens}\n\nVERSÃO ANTERIOR:\n{texto_corrido(anterior)}"
    )


def usuario(ancora: Ancora, feedback: str | None = None) -> str:
    base = f"FATOS DO DOCUMENTO:\n{fatos_em_texto(ancora)}\n\nEscreva o conteúdo."
    return f"{base}\n\n{feedback}" if feedback else base
