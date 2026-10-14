import { describe, expect, it } from "vitest";
import { duracaoTotal, faixaDeTempo, formatarTempo, palavrasDaFala, roteiroEmCsv, roteiroEmMarkdown, roteiroEmTexto } from "./roteiro";

const cenas = [
  { inicio_s: 0, fim_s: 5, fala: "A Selic subiu para 14,25%.", visual: "mão segurando uma nota", texto_tela: "Selic em alta" },
  { inicio_s: 5, fim_s: 65, fala: "O crédito fica \"mais caro\" | de novo.", visual: "casa", texto_tela: "" },
];

describe("roteiro", () => {
  it("formata o tempo em minutos e segundos", () => {
    expect(formatarTempo(0)).toBe("0:00");
    expect(formatarTempo(65)).toBe("1:05");
    expect(faixaDeTempo(cenas[0])).toBe("0:00–0:05");
    expect(duracaoTotal(cenas)).toBe(65);
    expect(palavrasDaFala(cenas)).toBe(13);
  });

  it("texto: um bloco por cena com narração, tela e ação", () => {
    const t = roteiroEmTexto("Copom (iniciante)", cenas);
    expect(t).toContain("ROTEIRO: Copom (iniciante)");
    expect(t).toContain("CENA 1  |  0:00–0:05");
    expect(t).toContain("NARRAÇÃO: A Selic subiu para 14,25%.");
    expect(t).toContain("NA TELA: Selic em alta");
    expect(t).toContain("AÇÃO E IMAGENS: mão segurando uma nota");
  });

  it("csv: separador ponto e vírgula, aspas escapadas e BOM para o Excel", () => {
    const c = roteiroEmCsv(cenas);
    expect(c.charCodeAt(0)).toBe(0xfeff);
    const linhas = c.slice(1).trim().split("\r\n");
    expect(linhas[0]).toBe('"Cena";"Tempo";"Narração";"Texto na tela";"Ação e imagens"');
    expect(linhas[1]).toBe('"1";"0:00–0:05";"A Selic subiu para 14,25%.";"Selic em alta";"mão segurando uma nota"');
    expect(linhas[2]).toContain('"O crédito fica ""mais caro"" | de novo."');
  });

  it("markdown: tabela sem quebrar com a barra vertical do texto", () => {
    const m = roteiroEmMarkdown("Copom", cenas);
    expect(m).toContain("| Tempo | Narração | Ação e imagens | Texto na tela |");
    expect(m).toContain("| 0:00–0:05 | A Selic subiu para 14,25%. | mão segurando uma nota | Selic em alta |");
    expect(m).toContain("de novo.");
    expect(m).not.toContain("| de novo");     // a barra do texto virou "/"
  });
});
