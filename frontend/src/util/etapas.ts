import type { Evento } from "../tipos";

export interface Etapa {
  id: "ler" | "fatos" | "escrever" | "guardar";
  nome: string;
  estado: "pendente" | "andando" | "feita";
  inicio: number | null;     // segundos desde o começo do pedido
  fim: number | null;
  detalhe?: string;
}

/** Tempo da etapa: o que já passou, ou o que está passando agora. */
export function duracao(e: Etapa, agora: number): number | null {
  if (e.inicio === null) return null;
  return Math.max(0, (e.fim ?? agora) - e.inicio);
}

export function formatarSegundos(s: number): string {
  if (s < 10) return `${s.toFixed(1).replace(".", ",")} s`;
  if (s < 60) return `${Math.round(s)} s`;
  const m = Math.floor(s / 60), r = Math.round(s % 60);
  return `${m} min ${String(r).padStart(2, "0")} s`;
}

/** As etapas do processamento, deduzidas dos eventos que o servidor envia (cada um traz `t`, os segundos desde o pedido). */
export function etapasDosEventos(eventos: Evento[], total: number): Etapa[] {
  const quando = (tipo: string) => eventos.find((e) => e.tipo === tipo)?.t ?? null;
  const fins = eventos.filter((e) => e.tipo === "ramo_fim");
  const doCache = eventos.some((e) => e.tipo === "cache");
  const fimGeral = quando("fim");

  const documento = quando("documento");
  const extraindo = quando("extraindo") ?? documento;
  const ancora = quando("ancora");
  const todosProntos = fins.length >= total ? fins[fins.length - 1].t : null;

  const ler: Etapa = {
    id: "ler", nome: doCache ? "Buscar o resultado guardado" : "Ler o documento", estado: "pendente",
    inicio: 0, fim: doCache ? (quando("cache") ?? fimGeral) : documento,
  };
  const fatos: Etapa = { id: "fatos", nome: "Extrair os fatos principais", estado: "pendente", inicio: extraindo, fim: ancora };
  const escrever: Etapa = {
    id: "escrever", nome: "Escrever e conferir cada conteúdo", estado: "pendente",
    inicio: ancora, fim: todosProntos, detalhe: `${fins.length} de ${total} prontos`,
  };
  const guardar: Etapa = { id: "guardar", nome: "Guardar o resultado", estado: "pendente", inicio: todosProntos, fim: fimGeral };

  const etapas = doCache ? [ler] : [ler, fatos, escrever, guardar];
  let anteriorFeita = true;
  for (const e of etapas) {
    if (e.fim !== null) e.estado = "feita";
    else if (anteriorFeita && e.inicio !== null) e.estado = "andando";
    else e.inicio = null;
    anteriorFeita = e.estado === "feita";
  }
  return etapas;
}
