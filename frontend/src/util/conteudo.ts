import type { Conteudo } from "../tipos";

/** Texto corrido de um conteúdo, o mesmo que o avaliador mede no servidor. */
export function textoDe(c: Conteudo | null): string {
  if (!c) return "";
  if ("corpo" in c) return `${c.titulo}\n${c.corpo}\n${c.conclusao}`;
  if ("slides" in c) return c.slides.join("\n");
  return c.cenas.map((x) => x.fala).join("\n");
}

export const dataBr = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "data não registrada";
