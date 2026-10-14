// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { config, glossario, resultado } from "../fixtures";
import type { Evento } from "../tipos";
import Andamento from "./Andamento";
import Entrada from "./Entrada";
import Historico from "./Historico";
import Mapa from "./Mapa";
import Resultado from "./Resultado";

beforeEach(() => { window.scrollTo = vi.fn(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const botao = (nome: RegExp | string) => screen.getByRole("button", { name: nome });
const marcados = (c: HTMLElement) => [...c.querySelectorAll("article mark.termo")];   // só no texto, não na legenda
const nivel = (nome: RegExp) => within(screen.getByRole("group", { name: "Nível" })).getByRole("button", { name: nome });
const formato = (nome: RegExp) => within(screen.getByRole("group", { name: "Formato" })).getByRole("button", { name: nome });
const cartao = () => screen.getByRole("region", { name: /(Iniciante|Intermediário|Avançado), / });

describe("Resultado", () => {
  const montar = () => render(<Resultado resultado={resultado} config={config} glossario={glossario} onNovo={vi.fn()} />);

  it("resume quantos conteúdos passaram e quantos foram reescritos", () => {
    montar();
    expect(screen.getByText("8 de 9")).toBeTruthy();
    expect(screen.getByText("conteúdos aprovados")).toBeTruthy();
    expect(screen.getByText("reescritos após a conferência").previousSibling?.textContent).toBe("2");
    expect(screen.getByText("Ata do Copom nº 281")).toBeTruthy();
    expect(screen.getByRole("link", { name: /documento original/ }).getAttribute("href")).toBe("https://www.bcb.gov.br/ata.pdf");
  });

  it("começa no primeiro conteúdo, com a versão final aprovada", () => {
    const { container } = montar();
    expect(screen.getByText("Iniciante · Artigo")).toBeTruthy();
    expect(container.textContent).toContain("A Selic, que é a taxa básica de juros, subiu para 14,25%");
    expect(container.textContent).not.toContain("hiato do produto negativo");   // a versão reprovada não aparece como texto final
    expect(within(cartao()).getByText("▲ Aprovado")).toBeTruthy();
  });

  it("marca só jargão: Selic sim; juros (nível 1) e termo ambíguo não", () => {
    const { container } = montar();
    const m = marcados(container);
    expect(m.map((x) => x.textContent)).toEqual(["Selic"]);
    expect(m[0].getAttribute("title")).toContain("taxa básica de juros da economia");
    expect(m[0].className).toContain("n2");
  });

  it("o interruptor tira as marcações", () => {
    const { container } = montar();
    fireEvent.click(screen.getByLabelText(/Marcar termos técnicos/));
    expect(marcados(container)).toHaveLength(0);
  });

  it("trocar o nível e o formato mostra outro conteúdo", () => {
    const { container } = montar();
    fireEvent.click(nivel(/Avançado/));
    expect(screen.getByText("Avançado · Artigo")).toBeTruthy();
    expect(container.textContent).toContain("Política monetária");
    fireEvent.click(formato(/Carrossel/));
    expect(screen.getByText("Avançado · Carrossel")).toBeTruthy();
    expect(screen.getByText("Gancho curto")).toBeTruthy();
    expect(screen.getByText("Gancho")).toBeTruthy();
    fireEvent.click(formato(/Vídeo curto/));
    expect(container.textContent).toContain("A Selic subiu.");   // "Selic" está marcada, então o texto vem em pedaços
    expect(screen.getByText("Gancho visual: seta para cima")).toBeTruthy();
  });

  it("um conteúdo bloqueado mostra o motivo em linguagem simples", () => {
    montar();
    fireEvent.click(formato(/Vídeo curto/));
    expect(within(cartao()).getByText("▼ Bloqueado")).toBeTruthy();
    expect(screen.getByText(/Passou em \d de 6 conferências/)).toBeTruthy();
    expect(screen.getByText(/roteiro marca 70s/)).toBeTruthy();   // motivo da conferência de formato
    expect(screen.getByText("Dentro dos limites do formato")).toBeTruthy();
  });

  it("comparar mostra os 3 níveis do mesmo formato e trava o seletor de nível", () => {
    const { container } = montar();
    fireEvent.click(screen.getByLabelText(/Comparar os 3 níveis/));
    expect(screen.getByText("Artigo: os 3 níveis")).toBeTruthy();
    expect(container.querySelectorAll(".coluna")).toHaveLength(3);
    expect(container.textContent).toContain("Selic a 14,25%");          // intermediário
    expect(container.textContent).toContain("Política monetária");      // avançado
    expect((nivel(/Iniciante/) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/Comparar os 3 níveis/));
    expect(container.querySelectorAll(".coluna")).toHaveLength(0);
  });

  it("a visão geral leva ao conteúdo clicado", () => {
    montar();
    const geral = screen.getByText("Visão geral dos 9 conteúdos").closest("details")!;
    fireEvent.click(within(geral).getByRole("button", { name: /Avançado, Vídeo curto/ }));
    expect(screen.getByText("Avançado · Vídeo curto")).toBeTruthy();
    expect(window.scrollTo).toHaveBeenCalled();
  });

  it("a fonte lista os fatos com o trecho literal do documento", () => {
    montar();
    const fonte = screen.getByText("Fatos e fonte do documento").closest("details")!;
    expect(within(fonte).getByText("O Copom elevou a Selic para 14,25%")).toBeTruthy();
    expect(within(fonte).getByText("O Copom elevou a taxa Selic para 14,25% ao ano")).toBeTruthy();
    expect(within(fonte).getByText(/outros 1, descartados/)).toBeTruthy();
    expect(within(fonte).getByText(/escrito por gerador-x, revisado por juiz-y/)).toBeTruthy();
  });

  it("'Novo documento' chama o retorno", () => {
    const onNovo = vi.fn();
    render(<Resultado resultado={resultado} config={config} glossario={glossario} onNovo={onNovo} />);
    fireEvent.click(botao("Novo documento"));
    expect(onNovo).toHaveBeenCalledOnce();
  });
});

describe("Avaliação", () => {
  it("conteúdo aprovado passa em todas as conferências e mostra o caminho de reescrita", () => {
    const { container } = render(<Resultado resultado={resultado} config={config} glossario={glossario} onNovo={vi.fn()} />);
    expect(screen.getByText("Passou em todas as conferências")).toBeTruthy();
    expect(screen.getByText("Leitura no nível certo")).toBeTruthy();
    expect(screen.getByText(/Índice de leitura 72.4 \(esperado de 60 a 100\)/)).toBeTruthy();
    expect(screen.getByText(/O texto foi escrito 2 vezes/)).toBeTruthy();
    expect(container.textContent).toContain("Tentativa 1: ▼ reprovada");
    expect(container.textContent).toContain("Problema: termo de nível 3 proibido");
    expect(container.textContent).toContain("O relatório de falhas foi entregue ao gerador");
  });

  it("'Ver o que mudou' mostra o que saiu e o que entrou entre a primeira e a última versão", () => {
    const { container } = render(<Resultado resultado={resultado} config={config} glossario={glossario} onNovo={vi.fn()} />);
    fireEvent.click(botao("Ver o que mudou"));
    expect(container.querySelector(".diff del")?.textContent).toContain("hiato");
    expect([...container.querySelectorAll(".diff ins")].map((x) => x.textContent).join(" ")).toContain("taxa");
    expect(container.textContent).toMatch(/\d+% do texto mudou/);
    fireEvent.click(botao("Esconder o que mudou"));
    expect(container.querySelector(".diff")).toBeNull();
  });

  it("conteúdo escrito de primeira não oferece comparação", () => {
    render(<Resultado resultado={resultado} config={config} glossario={glossario} onNovo={vi.fn()} />);
    fireEvent.click(formato(/Carrossel/));
    expect(screen.getByText("Escrito de primeira")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ver o que mudou" })).toBeNull();
  });
});

describe("Mapa e andamento", () => {
  it("mostra o estado ao vivo de cada conteúdo", () => {
    render(<Mapa resultado={null} ao_vivo={{
      "iniciante|artigo": { fase: "gerando", tentativa: 1 },
      "iniciante|carrossel": { fase: "avaliado", tentativa: 2, aprovado: false },
      "iniciante|video": { fase: "avaliado", tentativa: 1, aprovado: true },
    }} ocupado />);
    expect(screen.getByText("Escrevendo…")).toBeTruthy();
    expect(screen.getByText("Refazendo…")).toBeTruthy();
    expect(screen.getByText("Finalizando…")).toBeTruthy();
    expect(screen.getAllByText("Na fila")).toHaveLength(6);
    expect(screen.getByText("tentativa 2")).toBeTruthy();
  });

  it("o resultado pinta mais forte quem aprovou com menos tentativas", () => {
    const { container } = render(<Mapa resultado={resultado} ao_vivo={{}} />);
    expect(container.querySelectorAll(".celula.bom-1")).toHaveLength(7);   // aprovados de primeira
    expect(container.querySelectorAll(".celula.bom-2")).toHaveLength(1);   // iniciante/artigo, 2 tentativas
    expect(container.querySelectorAll(".celula.ruim")).toHaveLength(1);
    expect(screen.getByText("▼ Bloqueado")).toBeTruthy();
    expect(screen.getAllByText("2 tentativas", { selector: ".miudo" })).toHaveLength(2);   // iniciante: artigo (aprovou) e vídeo (bloqueou)
  });

  it("andamento conta os conteúdos prontos e avisa quando veio do banco", () => {
    const eventos: Evento[] = [{ tipo: "ancora", t: 5, fatos: 10 }];
    const { rerender } = render(<Andamento eventos={eventos} ao_vivo={{ "iniciante|artigo": { fase: "fim", tentativa: 1, status: "aprovado" } }} />);
    expect(screen.getByText("1 de 9 conteúdos prontos")).toBeTruthy();
    rerender(<Andamento eventos={[{ tipo: "cache", t: 1 }]} ao_vivo={{}} />);
    expect(screen.getByText("Buscando o resultado guardado…")).toBeTruthy();
  });
});

describe("Entrada e histórico", () => {
  it("o botão só habilita com um assunto válido e envia o pedido com as opções", () => {
    const onGerar = vi.fn();
    render(<Entrada ocupado={false} erro={null} onGerar={onGerar} />);
    const gerar = botao("Gerar conteúdos") as HTMLButtonElement;
    expect(gerar.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Assunto/), { target: { value: "Copom" } });
    expect(gerar.disabled).toBe(false);
    fireEvent.change(screen.getByLabelText(/Gerar primeiro o nível/), { target: { value: "avancado" } });
    fireEvent.submit(gerar.closest("form")!);
    expect(onGerar).toHaveBeenCalledWith({ tipo: "termo", valor: "Copom" },
      { niveis: ["iniciante", "intermediario", "avancado"], formatos: ["artigo", "carrossel", "video"], prioritario: "avancado", tentativas: 3, forcar: false });
  });

  it("as sugestões preenchem o campo e a aba de link não existe", () => {
    render(<Entrada ocupado={false} erro={null} onGerar={vi.fn()} />);
    fireEvent.click(botao("Inflação"));
    expect((screen.getByLabelText(/Assunto/) as HTMLInputElement).value).toBe("Inflação");
    expect(screen.queryByRole("tab", { name: "Um link" })).toBeNull();
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Um assunto", "Um PDF"]);
    expect((botao("Gerar conteúdos") as HTMLButtonElement).disabled).toBe(false);
  });

  it("aba de PDF pede o arquivo e mostra erro e estado ocupado", () => {
    const { rerender } = render(<Entrada ocupado={false} erro="A fonte respondeu com erro 404." onGerar={vi.fn()} />);
    expect(screen.getByRole("alert").textContent).toContain("404");
    fireEvent.click(screen.getByRole("tab", { name: "Um PDF" }));
    expect(screen.getByLabelText(/Arquivo PDF/)).toBeTruthy();
    expect((botao("Gerar conteúdos") as HTMLButtonElement).disabled).toBe(true);
    rerender(<Entrada ocupado erro={null} onGerar={vi.fn()} />);
    expect((botao("Gerando…") as HTMLButtonElement).disabled).toBe(true);
  });

  it("histórico lista as execuções e abre a escolhida", () => {
    const onAbrir = vi.fn();
    render(<Historico onAbrir={onAbrir} itens={[
      { id: "a1", documento: "d1", origem: "Copom", url: null, tipo: "termo", escopo: "publico", criado_em: "2026-10-11T16:29:00Z", ramos: 9, aprovados: 7 },
      { id: "b2", documento: "d2", origem: "meu.pdf", url: null, tipo: "pdf", escopo: "sessao", criado_em: "2026-10-11T17:00:00Z", ramos: 9, aprovados: 3 },
    ]} />);
    expect(screen.getByText("7 de 9 aprovados")).toBeTruthy();
    expect(screen.getByText(/só você vê/)).toBeTruthy();
    fireEvent.click(screen.getByText("meu.pdf"));
    expect(onAbrir).toHaveBeenCalledWith("b2");
  });

  it("histórico vazio explica o que acontece", () => {
    render(<Historico itens={[]} onAbrir={vi.fn()} />);
    expect(screen.getByText(/Nada gerado ainda/)).toBeTruthy();
  });
});

/* ---------- a aplicação inteira, com o servidor simulado ---------- */

class FalsoEventSource {
  static ultimo: FalsoEventSource | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  fechado = false;
  constructor(public url: string) { FalsoEventSource.ultimo = this; }
  close() { this.fechado = true; }
  emitir(e: Partial<Evento>) { this.onmessage?.({ data: JSON.stringify({ t: 1, ...e }) }); }
}

function servidor(rotas: Record<string, unknown>) {
  const chamadas: { url: string; metodo: string; corpo?: string }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    chamadas.push({ url, metodo: init?.method ?? "GET", corpo: typeof init?.body === "string" ? init.body : undefined });
    const chave = Object.keys(rotas).find((r) => url.startsWith(r));
    if (!chave) return new Response(JSON.stringify({ detail: "não encontrado" }), { status: 404 });
    const v = rotas[chave];
    return new Response(JSON.stringify(typeof v === "function" ? (v as () => unknown)() : v), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  vi.stubGlobal("EventSource", FalsoEventSource);
  return chamadas;
}
const historicoApi = [{ id: "abc123", documento: "0203078de324aaaa", origem: "Ata do Copom nº 281", url: null, tipo: "termo", escopo: "publico", criado_em: "2026-10-11T16:29:00Z", ramos: 9, aprovados: 8 }];

describe("App", () => {
  it("abre uma execução do histórico e volta ao início", async () => {
    servidor({ "/api/config": config, "/api/glossario": glossario, "/api/execucoes/abc123/relacionados": [], "/api/execucoes/abc123": resultado, "/api/execucoes": historicoApi });
    render(<App />);
    fireEvent.click(await screen.findByText("Ata do Copom nº 281"));
    expect(await screen.findByText("Iniciante · Artigo")).toBeTruthy();
    expect(screen.getByText("8 de 9")).toBeTruthy();
    fireEvent.click(botao("Novo documento"));
    expect(await screen.findByText(/Transforme um documento financeiro/)).toBeTruthy();
  });

  it("gera um documento: acompanha o andamento e mostra o resultado", async () => {
    const chamadas = servidor({
      "/api/config": config, "/api/glossario": glossario, "/api/execucoes": [],
      "/api/jobs/job1": { id: "job1", status: "concluido", erro: null, eventos: [], resultado, entrada: { tipo: "termo", valor: "Copom" } },
      "/api/jobs": { id: "job1", sessao: null },
    });
    render(<App />);
    fireEvent.change(screen.getByLabelText(/Assunto/), { target: { value: "Copom" } });
    fireEvent.click(botao("Gerar conteúdos"));

    await screen.findByText("Gerando");
    const post = chamadas.find((c) => c.metodo === "POST")!;
    expect(post.url).toBe("/api/jobs");
    expect(JSON.parse(post.corpo!)).toMatchObject({ tipo: "termo", valor: "Copom", tentativas: 3 });

    await waitFor(() => expect(FalsoEventSource.ultimo).not.toBeNull());
    const es = FalsoEventSource.ultimo!;
    expect(es.url).toBe("/api/jobs/job1/eventos");
    act(() => { es.emitir({ tipo: "extraindo" }); });
    expect(await screen.findByText("Lendo o documento e extraindo os fatos…")).toBeTruthy();
    act(() => { es.emitir({ tipo: "ancora", fatos: 10, descartados: 2 }); es.emitir({ tipo: "gerando", nivel: "iniciante", formato: "artigo", tentativa: 1 }); });
    expect(await screen.findByText("Escrevendo…")).toBeTruthy();
    act(() => { es.emitir({ tipo: "ramo_fim", nivel: "iniciante", formato: "artigo", status: "aprovado", tentativas: 2 }); });
    expect(await screen.findByText("1 de 9 conteúdos prontos")).toBeTruthy();

    act(() => { es.emitir({ tipo: "fim", execucao: "abc123" }); });
    expect(await screen.findByText("Iniciante · Artigo")).toBeTruthy();
    expect(es.fechado).toBe(true);
  });

  it("mostra o erro do servidor e volta para o formulário", async () => {
    servidor({
      "/api/config": config, "/api/glossario": glossario, "/api/execucoes": [],
      "/api/jobs/job9": { id: "job9", status: "erro", erro: "Não há fonte oficial cadastrada para \"banana\".", eventos: [], resultado: null, entrada: { tipo: "termo", valor: "banana" } },
      "/api/jobs": { id: "job9", sessao: null },
    });
    render(<App />);
    fireEvent.change(screen.getByLabelText(/Assunto/), { target: { value: "banana" } });
    fireEvent.click(botao("Gerar conteúdos"));
    await waitFor(() => expect(FalsoEventSource.ultimo?.url).toBe("/api/jobs/job9/eventos"));
    act(() => { FalsoEventSource.ultimo!.emitir({ tipo: "erro", mensagem: "x" }); });
    expect((await screen.findByRole("alert")).textContent).toContain("Não há fonte oficial");
    expect(screen.getByText(/Transforme um documento financeiro/)).toBeTruthy();
  });

  it("recusa do servidor na criação do job vira mensagem na tela", async () => {
    servidor({ "/api/config": config, "/api/glossario": glossario, "/api/execucoes": [] });   // /api/jobs inexiste: 404
    render(<App />);
    fireEvent.change(screen.getByLabelText(/Assunto/), { target: { value: "Copom" } });
    fireEvent.click(botao("Gerar conteúdos"));
    expect((await screen.findByRole("alert")).textContent).toContain("não encontrado");
  });
});
