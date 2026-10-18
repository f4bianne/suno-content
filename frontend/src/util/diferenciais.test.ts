// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { resultado } from "../fixtures";
import { AVISO_IMAGEM, baixar, folhaSvg, nomeDoArquivo, promptImagem, slideSvg } from "./exportacao";


describe("exportação", () => {
  const carrossel = resultado.ramos.find((r) => r.formato === "carrossel")!;
  const video = resultado.ramos.find((r) => r.formato === "video")!;
  const artigo = resultado.ramos.find((r) => r.formato === "artigo")!;

  it("um slide é SVG válido, com o texto e a identidade da Suno", () => {
    const g = slideSvg("A Selic subiu & o crédito <encareceu>", 1, 5);
    const doc = new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${g}</svg>`, "image/svg+xml");
    expect(doc.querySelector("parsererror")).toBeNull();
    expect(doc.querySelector("g")?.getAttribute("id")).toBe("slide-2-corpo");
    const linhas = [...doc.querySelectorAll("tspan[y]")].map((t) => t.textContent);          // uma tspan por linha
    expect(linhas.length).toBeGreaterThan(1);
    expect(linhas.join(" ")).toBe("A Selic subiu & o crédito <encareceu>");                    // escapado e lido de volta
    expect(g).toContain("#D42126");
    expect(g).toContain("2 DE 5");
  });

  it("gancho é escuro e a conclusão tem rótulo próprio", () => {
    expect(slideSvg("Gancho", 0, 3)).toContain('fill="#131313"');
    expect(slideSvg("Gancho", 0, 3)).toContain("GANCHO");
    expect(slideSvg("Fim", 2, 3)).toContain("CONCLUSÃO");
    expect(slideSvg("Fim", 2, 3)).toContain('fill="#FFFFFF"');
  });

  it("a folha junta todos os slides lado a lado, cada um com nome", () => {
    const slides = ("slides" in carrossel.conteudo! ? carrossel.conteudo.slides : []);
    const svg = folhaSvg(slides);
    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
    expect(doc.querySelector("parsererror")).toBeNull();
    const grupos = [...doc.querySelectorAll("g[id^='slide-']")];
    expect(grupos).toHaveLength(slides.length);
    expect(grupos[0].getAttribute("id")).toBe("slide-1-gancho");
    expect(grupos[slides.length - 1].getAttribute("id")).toBe(`slide-${slides.length}-conclusao`);
    expect(doc.documentElement.getAttribute("width")).toBe(String(slides.length * 1080 + (slides.length - 1) * 80));
    expect(doc.documentElement.getAttribute("height")).toBe("1080");
  });

  it("o nome do arquivo não tem acento nem espaço", () => {
    expect(nomeDoArquivo({ origem: "Ata do Copom nº 281" }, { nivel: "iniciante", formato: "carrossel" }, "svg")).toBe("ata-do-copom-n-281-iniciante-carrossel.svg");
  });

  it("o prompt de imagem do carrossel traz um item por slide e o aviso", () => {
    const p = promptImagem(resultado, carrossel);
    expect(p).toContain("Imagem 1 (quadrada, 1080x1080)");
    expect(p).toContain("Imagem 5");
    expect(p).toContain("A Selic subiu para 14,25%");
    expect(p).toContain("sem qualquer texto ou número escrito na imagem");
    expect(p).toContain(AVISO_IMAGEM);
  });

  it("prompt de imagem só existe para carrossel", () => {
    expect(promptImagem(resultado, video)).toBe("");
    expect(promptImagem(resultado, artigo)).toBe("");
    expect(promptImagem(resultado, { ...carrossel, conteudo: null })).toBe("");
  });

  it("baixar cria o arquivo e limpa o link temporário", () => {
    const criar = vi.fn(() => "blob:x");
    const revogar = vi.fn();
    Object.assign(URL, { createObjectURL: criar, revokeObjectURL: revogar });
    const clique = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    baixar("a.svg", "<svg/>", "image/svg+xml");
    expect(criar).toHaveBeenCalledOnce();
    expect(clique).toHaveBeenCalledOnce();
    expect(revogar).toHaveBeenCalledWith("blob:x");
    expect(document.querySelector("a[download]")).toBeNull();
  });
});
