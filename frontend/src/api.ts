import type { Config, Formato, Job, Nivel, Processamento, Relacionado, ResumoExecucao, TermoGlossario } from "./tipos";

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detalhe = r.statusText;
    try {
      const d = await r.json();
      detalhe = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch { /* resposta sem corpo */ }
    throw new Error(detalhe);
  }
  return r.json() as Promise<T>;
}

export interface Opcoes { niveis: Nivel[]; formatos: Formato[]; prioritario: Nivel | null; tentativas: number; forcar?: boolean }

const SESSAO = "suno_sessao";
/** A sessão guarda quais PDFs enviados são seus. Também pode vir no endereço (?sessao=nome), por exemplo para
 * abrir os resultados dos experimentos, que ficam na sessão "experimento". */
export function sessaoAtual(): string {
  try {
    const doEndereco = new URLSearchParams(window.location.search).get("sessao");
    if (doEndereco) { localStorage.setItem(SESSAO, doEndereco); return doEndereco; }
    return localStorage.getItem(SESSAO) ?? "";
  } catch { return ""; }
}
function guardarSessao(s: string | null | undefined): void {
  if (!s) return;
  try { localStorage.setItem(SESSAO, s); } catch { /* sem armazenamento: o PDF só não fica na lista */ }
}
const consultaSessao = () => (sessaoAtual() ? `?sessao=${encodeURIComponent(sessaoAtual())}` : "");

export async function criarJob(tipo: "termo" | "link", valor: string, o: Opcoes): Promise<{ id: string }> {
  return json(await fetch("/api/jobs", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo, valor, niveis: o.niveis, formatos: o.formatos, prioritario: o.prioritario, tentativas: o.tentativas, forcar: o.forcar ?? false }),
  }));
}

export async function criarJobPdf(arquivo: File, o: Opcoes): Promise<{ id: string }> {
  const q = new URLSearchParams({ nome: arquivo.name, niveis: o.niveis.join(","), formatos: o.formatos.join(",") });
  if (o.prioritario) q.set("prioritario", o.prioritario);
  if (o.forcar) q.set("forcar", "true");
  if (sessaoAtual()) q.set("sessao", sessaoAtual());
  const r = await json<{ id: string; sessao?: string }>(
    await fetch(`/api/jobs/pdf?${q}`, { method: "POST", headers: { "Content-Type": "application/pdf" }, body: arquivo }));
  guardarSessao(r.sessao);
  return r;
}

export const verJob = async (id: string) => json<Job>(await fetch(`/api/jobs/${id}`));
export const cancelarJob = async (id: string) => json<{ id: string; status: string }>(await fetch(`/api/jobs/${id}/cancelar`, { method: "POST" }));
export const listarExecucoes = async () => json<ResumoExecucao[]>(await fetch(`/api/execucoes${consultaSessao()}`));
export const verExecucao = async (id: string) => json<Processamento>(await fetch(`/api/execucoes/${id}${consultaSessao()}`));
export const verRelacionados = async (id: string) => json<Relacionado[]>(await fetch(`/api/execucoes/${id}/relacionados${consultaSessao()}`));
export const verConfig = async () => json<Config>(await fetch("/api/config"));
export const verGlossario = async () => json<TermoGlossario[]>(await fetch("/api/glossario"));
