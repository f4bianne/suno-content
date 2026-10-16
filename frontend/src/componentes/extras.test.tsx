// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { config, glossario, resultado } from "../fixtures";
import type { Processamento, ResumoExecucao } from "../tipos";
import ExportarDesign from "./ExportarDesign";
import OutrasVersoes from "./OutrasVersoes";
import VejaTambem from "./VejaTambem";

beforeEach(() => { window.scrollTo = vi.fn(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

const botao = (nome: RegExp | string) => screen.getByRole("button", { name: nome });
const ramoDe = (n: string, f: string) => resultado.ramos.find((r) => r.nivel === n && r.formato === f)!;
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status, headers: { "Content-Type": "application/json" } });

describe("ExportarDesign", () => {
  it("no carrossel, baixa os slides em SVG e copia o prompt", async () => {
    const criarUrl = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: criarUrl, revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const copiar = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: copiar }, configurable: true });

    render(<ExportarDesign resultado={resultado} ramo={ramoDe("iniciante", "carrossel")} />);
    expect(document.querySelectorAll(".slide-miniatura")).toHaveLength(5);          // um cartão por slide
    fireEvent.click(botao("Folha única para o Figma (SVG)"));
    fireEvent.click(screen.getAllByRole("button", { name: "SVG" })[0]);             // um slide separado
    expect(criarUrl).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("button", { name: /Baixar todos os slides \(PNG/ })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "PNG" })).toHaveLength(5);
    expect(document.querySelector(".alerta-suave")).not.toBeNull();    // aviso sobre imagens geradas por IA

    fireEvent.click(botao("Copiar prompt"));
    await waitFor(() => expect(botao("Copiado")).toBeTruthy());
    expect(copiar).toHaveBeenCalledTimes(1);
    expect(String((copiar.mock.calls[0] as unknown[])[0])).toContain("Selic");
  });

  it("no vídeo, oferece o roteiro para copiar e baixar em planilha, texto e tabela", async () => {
    const criarUrl = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: criarUrl, revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const copiar = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: copiar }, configurable: true });

    render(<ExportarDesign resultado={resultado} ramo={ramoDe("intermediario", "video")} />);
    fireEvent.click(botao("Baixar planilha (.csv)"));
    fireEvent.click(botao("Baixar texto (.txt)"));
    fireEvent.click(botao("Baixar tabela (.md)"));
    expect(criarUrl).toHaveBeenCalledTimes(3);
    fireEvent.click(botao("Copiar roteiro"));
    await waitFor(() => expect(botao("Roteiro copiado")).toBeTruthy());
    expect(String((copiar.mock.calls[0] as unknown[])[0])).toContain("NARRAÇÃO: A Selic subiu.");
  });

  it("no artigo, oferece copiar e baixar em html, markdown e texto, sem prompt de imagem", async () => {
    const criarUrl = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: criarUrl, revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const copiar = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: copiar }, configurable: true });

    render(<ExportarDesign resultado={resultado} ramo={ramoDe("iniciante", "artigo")} />);
    fireEvent.click(botao("Baixar página (.html)"));
    fireEvent.click(botao("Baixar Markdown (.md)"));
    fireEvent.click(botao("Baixar texto (.txt)"));
    expect(criarUrl).toHaveBeenCalledTimes(3);
    fireEvent.click(botao("Copiar artigo"));
    await waitFor(() => expect(botao("Artigo copiado")).toBeTruthy());
    expect(String((copiar.mock.calls[0] as unknown[])[0])).toContain("Fonte: Ata do Copom nº 281");
    expect(screen.queryByText(/Prompt para IA de imagem/)).toBeNull();
    expect(document.querySelectorAll(".slide-miniatura")).toHaveLength(0);
  });

  it("só o carrossel tem prompt de imagem; vídeo e artigo não", () => {
    const { unmount } = render(<ExportarDesign resultado={resultado} ramo={ramoDe("iniciante", "carrossel")} />);
    expect(screen.getByText(/Prompt para IA de imagem/)).toBeTruthy();
    unmount();
    render(<ExportarDesign resultado={resultado} ramo={ramoDe("iniciante", "video")} />);
    expect(screen.queryByText(/Prompt para IA de imagem/)).toBeNull();
    expect(screen.queryByLabelText(/Prompt \(você pode editar/)).toBeNull();
  });
});

describe("OutrasVersoes", () => {
  const item = (id: string, documento: string): ResumoExecucao =>
    ({ id, documento, origem: "Ata", url: null, tipo: "termo", escopo: "publico", criado_em: "2026-10-12T10:00:00Z", ramos: 9, aprovados: 7 });
  const props = { atual: resultado, nivel: "iniciante" as const, formato: "artigo" as const, termos: glossario, config };

  it("com uma geração só, explica como criar a segunda", () => {
    render(<OutrasVersoes {...props} historico={[item("abc123", "0203078de324aaaa")]} />);
    expect(screen.getByText(/gerado uma vez só/)).toBeTruthy();
  });

  it("mostra só versões do mesmo documento, carrega a escolhida e exibe a diferença", async () => {
    const outra: Processamento = JSON.parse(JSON.stringify(resultado));
    outra.execucao_id = "zzz";
    outra.ramos[0].conteudo = { titulo: "Juros caem", corpo: "A Selic caiu para 13%.", conclusao: "Fim." };
    outra.ramos[0].tentativas[outra.ramos[0].tentativas.length - 1].conteudo = outra.ramos[0].conteudo;
    vi.stubGlobal("fetch", vi.fn(async () => json(outra)));

    render(<OutrasVersoes {...props} historico={[item("abc123", "0203078de324aaaa"), item("zzz", "0203078de324aaaa"), item("w", "outro")]} />);
    const seletor = screen.getByLabelText("Comparar com") as HTMLSelectElement;
    expect(seletor.options.length).toBe(2);                    // "Escolha..." + uma versão (a atual e a de outro documento ficam de fora)
    fireEvent.change(seletor, { target: { value: "zzz" } });

    expect(await screen.findByText("Outra versão")).toBeTruthy();
    expect(screen.getByText("Esta versão")).toBeTruthy();
    fireEvent.click(botao("Ver a diferença entre as duas"));
    expect(screen.getByText(/do texto é diferente/)).toBeTruthy();
    expect(document.querySelector(".diff del")).not.toBeNull();
    expect(document.querySelector(".diff ins")).not.toBeNull();
  });

  it("mostra o erro se a outra versão não carregar", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "sumiu" }, 404)));
    render(<OutrasVersoes {...props} historico={[item("abc123", "0203078de324aaaa"), item("zzz", "0203078de324aaaa")]} />);
    fireEvent.change(screen.getByLabelText("Comparar com"), { target: { value: "zzz" } });
    expect((await screen.findByRole("alert")).textContent).toContain("sumiu");
  });
});

describe("VejaTambem", () => {
  const rel = { id: "r1", origem: "Ata do Copom nº 280", criado_em: "2026-09-01T10:00:00Z", ramos: 9, aprovados: 9, entidades_comuns: ["Selic", "IPCA"], afinidade: 0.5 };

  it("lista os documentos com as mesmas entidades e abre o escolhido", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([rel])));
    const onAbrir = vi.fn();
    render(<VejaTambem execucaoId="abc123" onAbrir={onAbrir} />);
    expect(screen.getByText(/Procurando/)).toBeTruthy();
    fireEvent.click(await screen.findByText("Ata do Copom nº 280"));
    expect(onAbrir).toHaveBeenCalledWith("r1");
    expect(screen.getByText(/Também fala de Selic, IPCA/)).toBeTruthy();
  });

  it("sem relacionados, ou se a busca falhar, explica sem quebrar a tela", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([])));
    const { unmount } = render(<VejaTambem execucaoId="abc123" onAbrir={vi.fn()} />);
    expect(await screen.findByText(/Nenhum outro documento/)).toBeTruthy();
    unmount();
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "erro" }, 500)));
    render(<VejaTambem execucaoId="abc123" onAbrir={vi.fn()} />);
    expect(await screen.findByText(/Nenhum outro documento/)).toBeTruthy();
  });

  it("sem identificador de execução, nem consulta o servidor", () => {
    const f = vi.fn(); vi.stubGlobal("fetch", f);
    render(<VejaTambem execucaoId={null} onAbrir={vi.fn()} />);
    expect(screen.getByText(/Nenhum outro documento/)).toBeTruthy();
    expect(f).not.toHaveBeenCalled();
  });
});

describe("Entrada: escolher o que gerar", () => {
  it("envia só os níveis e formatos marcados e bloqueia quando nada está marcado", async () => {
    const { default: Entrada } = await import("./Entrada");
    const onGerar = vi.fn();
    render(<Entrada ocupado={false} erro={null} onGerar={onGerar} />);
    fireEvent.change(screen.getByLabelText(/Assunto/), { target: { value: "Copom" } });
    const niveis = within(screen.getByRole("group", { name: "Níveis" }));
    const formatos = within(screen.getByRole("group", { name: "Formatos" }));
    fireEvent.click(niveis.getByLabelText("Intermediário"));
    fireEvent.click(niveis.getByLabelText("Avançado"));
    fireEvent.click(formatos.getByLabelText("Vídeo curto"));
    expect(screen.getByText(/2 conteúdos/)).toBeTruthy();
    fireEvent.submit(botao("Gerar conteúdos").closest("form")!);
    expect(onGerar).toHaveBeenCalledWith({ tipo: "termo", valor: "Copom" },
      { niveis: ["iniciante"], formatos: ["artigo", "carrossel"], prioritario: null, tentativas: 2, forcar: false });
    fireEvent.click(niveis.getByLabelText("Iniciante"));
    expect((botao("Gerar conteúdos") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/pelo menos um nível/)).toBeTruthy();
  });
});

describe("Mapa durante a geração parcial", () => {
  it("só as células pedidas ficam 'Na fila'; as outras dizem 'Não pedido'", async () => {
    const { default: Mapa } = await import("./Mapa");
    render(<Mapa resultado={null} ao_vivo={{}} ocupado pedidos={["iniciante|carrossel"]} />);
    expect(screen.getAllByText("Na fila")).toHaveLength(1);
    expect(screen.getAllByText("Não pedido")).toHaveLength(8);
  });
});

describe("Avaliacao: plano do revisor", () => {
  it("mostra o plano que o revisor montou entre uma tentativa e a seguinte", async () => {
    const { default: Avaliacao } = await import("./Avaliacao");
    const base = ramoDe("iniciante", "artigo");
    const ramo = {
      ...base,
      tentativas: base.tentativas.map((t, i) => i === 0
        ? { ...t, metricas: { ...t.metricas, plano_revisao: { diagnostico: "Usou jargão sem explicar.", acoes: ["Explique a Selic no primeiro parágrafo."], manter: ["O número 14,25"] } } }
        : t),
    };
    render(<Avaliacao ramo={ramo} config={config} />);
    expect(screen.getByText("O revisor leu as falhas e montou um plano para a reescrita")).toBeTruthy();
    expect(screen.getByText("Usou jargão sem explicar.")).toBeTruthy();
    expect(screen.getByText("Explique a Selic no primeiro parágrafo.")).toBeTruthy();
    expect(screen.getByText(/Manter: O número 14,25/)).toBeTruthy();
  });

  it("sem plano, mantém a explicação antiga", async () => {
    const { default: Avaliacao } = await import("./Avaliacao");
    render(<Avaliacao ramo={ramoDe("iniciante", "artigo")} config={config} />);
    expect(screen.getByText(/O relatório de falhas foi entregue ao gerador/)).toBeTruthy();
  });
});

describe("Avaliacao: definição acrescentada pelo sistema", () => {
  it("avisa quais termos ganharam a definição do glossário", async () => {
    const { default: Avaliacao } = await import("./Avaliacao");
    const base = ramoDe("iniciante", "artigo");
    const ramo = { ...base, tentativas: base.tentativas.map((t, i) => i === 0 ? { ...t, metricas: { ...t.metricas, explicacoes_inseridas: ["Selic", "CDB"] } } : t) };
    render(<Avaliacao ramo={ramo} config={config} />);
    expect(screen.getByText("O sistema acrescentou a definição do glossário em: Selic, CDB.")).toBeTruthy();
  });
});
