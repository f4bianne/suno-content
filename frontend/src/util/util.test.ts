import { describe, expect, it } from "vitest";
import type { Config, Tentativa, TermoGlossario } from "../tipos";
import { checagens, falhasDaRegra, faixaFlesch, fleschNaFaixa, resumir } from "./avaliacao";
import { segmentar, termosParaDestacar } from "./destaque";
import { diferenca, proporcaoAlterada } from "./diff";

const config = {
  niveis: ["iniciante", "intermediario", "avancado"], formatos: ["artigo", "carrossel", "video"],
  limiares: {
    iniciante: { flesch: [60, 100], cobertura_minima: 0.8 },
    intermediario: { flesch: [40, 60], cobertura_minima: 0.8 },
    avancado: { flesch: [0, 50], flesch_video: [0, 60], cobertura_minima: 0.9 },
  },
} as unknown as Config;

const tentativa = (falhas: string[], extra: Partial<Tentativa> = {}): Tentativa => ({
  n: 1, aprovado: falhas.length === 0, falhas, metricas: { flesch: 70, cobertura: 0.9 }, veredito: null, conteudo: null,
  segundos_geracao: 1, segundos_avaliacao: 1, chamadas_llm: 1, ...extra,
});
const veredito = { afirmacoes_sem_suporte: [], nota_fidelidade: 5, criterios_atendidos: [], criterios_nao_atendidos: [], nota_adequacao_nivel: 5, fatos_confirmados: [], fatos_ausentes: [], justificativa: "" };

describe("avaliacao", () => {
  it("falhasDaRegra filtra pela etiqueta e tira o prefixo", () => {
    const t = tentativa(["[glossario] termo X sem explicacao.", "[cobertura] 50%", "[numeros] numero 7"]);
    expect(falhasDaRegra(t, "glossario")).toEqual(["termo X sem explicacao."]);
    expect(falhasDaRegra(t, "cobertura", "numeros")).toHaveLength(2);
    expect(falhasDaRegra(t, "juiz")).toEqual([]);
  });

  it("resumir pega a primeira frase e limita o tamanho", () => {
    expect(resumir("Primeira frase. Segunda frase.")).toBe("Primeira frase.");
    expect(resumir("a".repeat(400), 50)).toHaveLength(50);
  });

  it("conteudo aprovado passa em tudo, inclusive no juiz", () => {
    const c = checagens(tentativa([], { veredito }), { nivel: "iniciante", formato: "artigo" }, config);
    expect(c.map((x) => x.estado)).toEqual(["ok", "ok", "ok", "ok", "ok", "ok"]);
    expect(c[5].detalhe).toContain("5/5");
  });

  it("uma regra que falha aparece com o motivo e o juiz nao chega a rodar", () => {
    const t = tentativa(["[glossario] termo de nivel 3 proibido: 'hiato do produto' em \"...\". Troque o termo."]);
    const c = checagens(t, { nivel: "iniciante", formato: "artigo" }, config);
    const termos = c.find((x) => x.id === "termos")!;
    expect(termos.estado).toBe("falhou");
    expect(termos.motivo).toContain("hiato do produto");
    expect(c.find((x) => x.id === "leitura")!.estado).toBe("ok");
    expect(c.find((x) => x.id === "juiz")!.estado).toBe("nao_rodou");
  });

  it("cobertura e numeros contam como fidelidade aos fatos", () => {
    const c = checagens(tentativa(["[numeros] numero '7' nao existe na ancora."]), { nivel: "avancado", formato: "artigo" }, config);
    expect(c.find((x) => x.id === "fatos")!.estado).toBe("falhou");
  });

  it("falha do juiz marca a revisao como falhou", () => {
    const t = tentativa(["[juiz] afirmacao sem suporte: A Selic vai a 20%"], { veredito: { ...veredito, nota_fidelidade: 2 } });
    const juiz = checagens(t, { nivel: "iniciante", formato: "artigo" }, config).find((x) => x.id === "juiz")!;
    expect(juiz.estado).toBe("falhou");
    expect(juiz.motivo).toContain("A Selic vai a 20%");
  });

  it("video tem faixa de leitura propria", () => {
    expect(faixaFlesch(config, { nivel: "avancado", formato: "video" })).toEqual([0, 60]);
    expect(faixaFlesch(config, { nivel: "avancado", formato: "artigo" })).toEqual([0, 50]);
    expect(faixaFlesch(null, { nivel: "avancado", formato: "artigo" })).toBeNull();
  });

  it("flesch acima de 100 ou abaixo de zero e limitado a escala", () => {
    expect(fleschNaFaixa(108, [60, 100])).toBe(true);
    expect(fleschNaFaixa(-5, [0, 50])).toBe(true);
    expect(fleschNaFaixa(45, [60, 100])).toBe(false);
  });
});

describe("diferenca", () => {
  it("textos iguais nao mudam", () => {
    const p = diferenca("a Selic subiu", "a Selic subiu");
    expect(p).toEqual([{ tipo: "igual", texto: "a Selic subiu" }]);
    expect(proporcaoAlterada(p)).toBe(0);
  });

  it("marca o que saiu e o que entrou", () => {
    const p = diferenca("a Selic subiu muito", "a Selic caiu muito");
    expect(p).toEqual([
      { tipo: "igual", texto: "a Selic" },
      { tipo: "removido", texto: "subiu" },
      { tipo: "adicionado", texto: "caiu" },
      { tipo: "igual", texto: "muito" },
    ]);
    expect(proporcaoAlterada(p)).toBeCloseTo(2 / 5);
  });

  it("textos totalmente diferentes e vazios", () => {
    expect(proporcaoAlterada(diferenca("um dois", "tres quatro"))).toBe(1);
    expect(diferenca("", "novo texto")).toEqual([{ tipo: "adicionado", texto: "novo texto" }]);
    expect(diferenca("", "")).toEqual([]);
  });

  it("textos longos nao travam", () => {
    const longo = Array.from({ length: 800 }, (_, i) => `p${i}`).join(" ");
    expect(diferenca(longo, `${longo} fim`).length).toBeGreaterThan(0);
  });
});

describe("destaque", () => {
  const termo = (nome: string, nivel: number, extra: Partial<TermoGlossario> = {}): TermoGlossario =>
    ({ termo: nome, nivel, formas: [nome], explicacao: `${nome} explicado`, ambiguo: false, ...extra });
  const gloss = [termo("Selic", 2, { formas: ["Selic", "taxa Selic"] }), termo("hiato do produto", 3), termo("CDI", 2), termo("juros", 1),
    termo("principal", 2, { ambiguo: true }), termo("curva de juros", 3)];

  it("so destaca jargao: tira nivel 1 e termos ambiguos", () => {
    expect(termosParaDestacar(gloss).map((t) => t.termo)).toEqual(["Selic", "hiato do produto", "CDI", "curva de juros"]);
  });

  it("corta o texto em pedacos e marca os termos", () => {
    const r = segmentar("A Selic subiu e o hiato do produto fechou.", termosParaDestacar(gloss));
    expect(r.map((x) => x.texto)).toEqual(["A ", "Selic", " subiu e o ", "hiato do produto", " fechou."]);
    expect(r.filter((x) => x.termo).map((x) => x.termo!.nivel)).toEqual([2, 3]);
  });

  it("forma mais longa vence", () => {
    const r = segmentar("a taxa Selic subiu", termosParaDestacar(gloss));
    expect(r.find((x) => x.termo)!.texto).toBe("taxa Selic");
  });

  it("sigla so casa em maiusculas e por palavra inteira", () => {
    const termos = termosParaDestacar(gloss);
    expect(segmentar("rende 100% do CDI", termos).some((x) => x.termo)).toBe(true);
    expect(segmentar("o cdi nao existe", termos).some((x) => x.termo)).toBe(false);
    expect(segmentar("ACDIA", termos).some((x) => x.termo)).toBe(false);
  });

  it("aceita plural e nao quebra com texto sem termos", () => {
    expect(segmentar("as curvas de juros", termosParaDestacar(gloss)).some((x) => x.termo)).toBe(false);
    expect(segmentar("duas curva de juros", termosParaDestacar(gloss)).some((x) => x.termo)).toBe(true);
    expect(segmentar("texto comum", termosParaDestacar(gloss))).toEqual([{ texto: "texto comum" }]);
    expect(segmentar("", [])).toEqual([{ texto: "" }]);
  });
});
