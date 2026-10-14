// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { listarExecucoes, sessaoAtual, verExecucao } from "./api";

beforeEach(() => { localStorage.clear(); window.history.pushState({}, "", "/"); });
afterEach(() => vi.restoreAllMocks());

describe("sessão", () => {
  it("sem sessão, as consultas vão sem o parâmetro", async () => {
    const f = vi.fn(async () => new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", f);
    await listarExecucoes();
    expect(f).toHaveBeenCalledWith("/api/execucoes");
  });

  it("a sessão vem do endereço, fica guardada e vai nas consultas", async () => {
    window.history.pushState({}, "", "/?sessao=experimento");
    expect(sessaoAtual()).toBe("experimento");
    window.history.pushState({}, "", "/");           // recarregou sem o parâmetro: continua guardada
    expect(sessaoAtual()).toBe("experimento");
    const f = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", f);
    await listarExecucoes();
    await verExecucao("x1");
    expect(f).toHaveBeenNthCalledWith(1, "/api/execucoes?sessao=experimento");
    expect(f).toHaveBeenNthCalledWith(2, "/api/execucoes/x1?sessao=experimento");
  });

  it("erro do servidor vira mensagem legível", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "execução não encontrada" }), { status: 404 })));
    await expect(verExecucao("zzz")).rejects.toThrow("execução não encontrada");
  });
});
