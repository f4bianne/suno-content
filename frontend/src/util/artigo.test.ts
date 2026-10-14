import { describe, expect, it } from "vitest";
import { resultado } from "../fixtures";
import { artigoEmHtml, artigoEmMarkdown, artigoEmTexto } from "./artigo";

const ramo = resultado.ramos[0];
const a = { titulo: "Juros <sobem>", corpo: "Primeiro parágrafo.\nSegundo & último.", conclusao: "Fique atento." };

describe("artigo exportado", () => {
  it("texto: título em caixa alta, parágrafos e a fonte no rodapé", () => {
    const t = artigoEmTexto(a, resultado, ramo);
    expect(t.startsWith("JUROS <SOBEM>")).toBe(true);
    expect(t).toContain("Primeiro parágrafo.\n\nSegundo & último.");
    expect(t).toContain("Fonte: Ata do Copom nº 281 (https://www.bcb.gov.br/ata.pdf). Nível Iniciante.");
  });

  it("markdown: título com # e fonte em itálico", () => {
    const m = artigoEmMarkdown(a, resultado, ramo);
    expect(m.startsWith("# Juros <sobem>")).toBe(true);
    expect(m).toContain("*Fonte: Ata do Copom");
  });

  it("html: escapa o texto e traz um parágrafo por quebra", () => {
    const h = artigoEmHtml(a, resultado, ramo);
    expect(h).toContain("<h1>Juros &lt;sobem&gt;</h1>");
    expect(h).toContain("<p>Segundo &amp; último.</p>");
    expect(h).toContain("<footer>");
    expect(h).not.toContain("<sobem>");
  });
});
