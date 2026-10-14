"""Prompts do gerador: perfil do nível, instruções do formato e relatório de falhas para a nova tentativa."""
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


def instrucao_formato(formato: str, cfg: dict) -> str:
    f = cfg["formatos"]
    if formato == "artigo":
        lo, hi = f["artigo"]["palavras"]
        return (f"FORMATO: artigo analítico para web ou newsletter, com título, corpo e conclusão. REGRA DURA: entre {lo + 30} e "
                f"{hi - 100} palavras no total (menos de {lo} é rejeitado). A conclusão é um parágrafo novo, sem repetir o corpo.")
    if formato == "carrossel":
        lo, hi = f["carrossel"]["slides"]
        c = f["carrossel"]["caracteres_por_slide"]
        return (f"FORMATO: carrossel. gancho (slide 1, que prende a atenção), slides_corpo (de {lo - 2} a {hi - 2} slides) e "
                f"conclusao (último slide). O total, contando gancho e conclusão, fica entre {lo} e {hi} slides. REGRA DURA: "
                f"cada slide tem no máximo {c - 30} caracteres (conte; slide acima de {c} é rejeitado). Cada slide de corpo "
                "traz uma ideia completa. Não cabe tudo: priorize os fatos mais importantes.")
    pmax, pps = f["video"]["duracao_maxima_s"], f["video"]["palavras_por_segundo"]
    limite = int((pmax - 10) * pps)
    return (f"FORMATO: roteiro de vídeo curto de no máximo {pmax - 5} segundos. Lista de cenas com inicio_s e fim_s (começa em 0, "
            f"sem lacunas, a última termina em até {pmax - 5}), fala (texto lido em voz alta) e visual (o que aparece na tela). "
            f"REGRA DURA: some todas as falas e use no máximo {limite} palavras (acima disso o vídeo passa de {pmax} s e é "
            "rejeitado). Não cabe tudo: priorize os fatos mais importantes. "
            "O visual da primeira cena é um gancho visual que prende a atenção.")


def sistema(nivel: str, formato: str, termos: list[Termo], cfg: dict) -> str:
    return (
        "Você adapta documentos financeiros oficiais brasileiros, em português do Brasil, para um público e um formato.\n"
        f"PÚBLICO: {PERFIL[nivel]}\n{regra_de_termos(nivel, termos)}\n{instrucao_formato(formato, cfg)}\n"
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
