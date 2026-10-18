import { describe, expect, it } from "vitest";
import type { Grafico } from "../tipos";
import { caber, cortar, medir, quebrar, type Caixa } from "./caber";
import { AREA, diagramar, graficoDoSlide, slideSvg } from "./exportacao";
import { desenharGrafico, numeroBr } from "./grafico";

const dentro = (c: Caixa, de: Caixa) =>
  c.x >= de.x - 0.5 && c.y >= de.y - 0.5 && c.x + c.largura <= de.x + de.largura + 0.5 && c.y + c.altura <= de.y + de.altura + 0.5;

// Gerador simples e determinístico, para os testes repetirem sempre os mesmos casos.
function sorteio(semente: number) {
  let s = semente;
  return () => { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648; };
}
const PALAVRAS = ["a", "Selic", "subiu", "inflação", "14,25%", "WWWWWWW", "mmmmmm", "IPCA", "expectativas", "R$ 5.216,00", "—",
  "desancoragem", "MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM", "ç", "ãõ", "intermediário"];
const frase = (r: () => number, n: number) => Array.from({ length: n }, () => PALAVRAS[Math.floor(r() * PALAVRAS.length)]).join(" ");

describe("medir e quebrar", () => {
  it("letras largas medem mais que estreitas, e negrito mais que normal", () => {
    expect(medir("WWWW", 20)).toBeGreaterThan(medir("iiii", 20) * 3);
    expect(medir("Selic", 20, true)).toBeGreaterThan(medir("Selic", 20));
    expect(medir("✓", 20)).toBeGreaterThan(medir("a", 20));             // fora da tabela conta como o mais largo
  });

  it("nenhuma linha passa da largura, nem com palavra maior que a linha", () => {
    const linhas = quebrar("a Selic subiu MMMMMMMMMMMMMMMMMMMMMMMMMMMMMM para 14,25% ao ano", 200, 30);
    expect(linhas.every((l) => medir(l, 30) <= 200)).toBe(true);
    expect(linhas.join("").replace(/\s/g, "")).toBe("aSelicsubiuMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMpara14,25%aoano");
  });

  it("cortar põe reticências só quando precisa", () => {
    expect(cortar("2026", 200, 20)).toBe("2026");
    const c = cortar("Crédito livre para pessoas físicas", 120, 20);
    expect(c.endsWith("…") && medir(c, 20) <= 120).toBe(true);
  });

  it("caber escolhe a maior fonte que cabe e nunca devolve algo maior que a caixa", () => {
    const r = sorteio(7);
    for (let i = 0; i < 300; i++) {
      const caixa = { largura: 200 + r() * 700, altura: 60 + r() * 600 };
      const e = caber(frase(r, 1 + Math.floor(r() * 80)), { ...caixa, tamanhoMax: 84, tamanhoMin: 28, negrito: r() > 0.5 });
      expect(e.altura).toBeLessThanOrEqual(caixa.altura);
      expect(e.largura).toBeLessThanOrEqual(caixa.largura);
    }
    expect(caber("Curto.", { largura: 888, altura: 714, tamanhoMax: 84, tamanhoMin: 32 }).tamanho).toBe(84);
  });
});

describe("gráfico", () => {
  const g = (x: Partial<Grafico> = {}): Grafico =>
    ({ slide: 1, tipo: "barras", titulo: "Projeções de inflação", rotulos: ["2026", "2027", "2028"], valores: [4.9, 4.3, 3.2], unidade: "%", ...x });
  const caixa = { x: 96, y: 400, largura: 888, altura: 480 };
  const cores = { tinta: "#222", apoio: "#767676", grade: "#D9D9D9", destaque: "#D42126" };

  it("escreve os números como nos fatos", () => {
    expect([4.9, 14.25, 5216, -0.5, 15, 0].map(numeroBr)).toEqual(["4,9", "14,25", "5.216", "-0,5", "15", "0"]);
    const svg = desenharGrafico(g(), caixa, cores).svg;
    expect(svg).toContain("4,9%");
    expect(svg).toContain("2028");
  });

  it("barras e linha, com qualquer dado permitido e alguns fora do limite, ficam dentro da caixa", () => {
    const r = sorteio(11);
    for (let i = 0; i < 300; i++) {
      const n = 1 + Math.floor(r() * 7);
      const grafico = g({
        tipo: r() > 0.5 ? "barras" : "linha",
        titulo: frase(r, 1 + Math.floor(r() * 12)),
        rotulos: Array.from({ length: n }, () => frase(r, 1 + Math.floor(r() * 3))),
        valores: Array.from({ length: n }, () => (r() - 0.3) * 10 ** Math.floor(r() * 5)),
        unidade: ["%", "p.p.", "R$ bi", "", "bilhões"][Math.floor(r() * 5)],
      });
      const c = { x: 96, y: 300 + r() * 200, largura: 888, altura: 300 + r() * 300 };
      const d = desenharGrafico(grafico, c, cores);
      for (const o of d.ocupado) expect(dentro(o, c), JSON.stringify({ o, c, grafico })).toBe(true);
    }
  });
});

describe("slide de 1080 px", () => {
  it("texto sozinho, de qualquer tamanho, fica na área do conteúdo", () => {
    const r = sorteio(3);
    for (let i = 0; i < 200; i++) {
      const papel = (["gancho", "corpo", "conclusao"] as const)[i % 3];
      const d = diagramar(frase(r, 1 + Math.floor(r() * 90)), papel, undefined, papel === "gancho");
      for (const o of d.ocupado) expect(dentro(o, AREA)).toBe(true);
    }
  });

  it("texto em cima e gráfico embaixo, sem se encostar, dentro da área", () => {
    const r = sorteio(5);
    for (let i = 0; i < 200; i++) {
      const n = 2 + Math.floor(r() * 5);
      const grafico: Grafico = { slide: 1, tipo: i % 2 ? "linha" : "barras", titulo: frase(r, 6), unidade: "%",
        rotulos: Array.from({ length: n }, (_, k) => String(2020 + k)), valores: Array.from({ length: n }, () => r() * 20 - 5) };
      const d = diagramar(frase(r, 1 + Math.floor(r() * 40)), "corpo", grafico, false);
      for (const o of d.ocupado) expect(dentro(o, AREA)).toBe(true);
      const [texto, ...resto] = d.ocupado;
      expect(Math.min(...resto.map((o) => o.y))).toBeGreaterThanOrEqual(texto.y + texto.altura);
    }
  });

  it("o gráfico só entra nos slides do corpo", () => {
    const grafico: Grafico = { slide: 0, tipo: "barras", titulo: "T", rotulos: ["a", "b"], valores: [1, 2], unidade: "" };
    expect(slideSvg("Gancho", 0, 5, 0, grafico)).not.toContain('class="grafico"');
    expect(slideSvg("Corpo", 1, 5, 0, { ...grafico, slide: 1 })).toContain('class="grafico"');
  });
});

describe("gráficos guardados em formato antigo", () => {
  it("são ignorados em vez de quebrar o desenho", () => {
    const antigo = { slide: 3, titulo: "PIB", rotulos: ["1T", "2T"], valores: ["1,1%", "0,5%"] } as unknown as Grafico;
    expect(graficoDoSlide([antigo], 3)).toBeUndefined();
    const atual: Grafico = { slide: 3, tipo: "barras", titulo: "PIB", rotulos: ["1T", "2T"], valores: [1.1, 0.5], unidade: "%" };
    expect(graficoDoSlide([antigo, atual], 3)).toBe(atual);
  });
});
