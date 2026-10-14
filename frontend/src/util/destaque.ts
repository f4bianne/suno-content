import type { TermoGlossario } from "../tipos";

export interface Trecho { texto: string; termo?: TermoGlossario }

const escapar = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const LETRA = "[0-9A-Za-zÀ-ÿ]";
const ehSigla = (f: string) => f === f.toUpperCase() && /[A-Z]/.test(f);

/** Só os termos que são jargão (níveis 2 e 3) e que não têm uso comum fora de finanças. Nível 1 poluiria o texto. */
export function termosParaDestacar(glossario: TermoGlossario[]): TermoGlossario[] {
  return glossario.filter((t) => t.nivel >= 2 && !t.ambiguo);
}

/** Corta o texto em pedaços; os que casam com o glossário vêm com o termo. A forma mais longa vence. */
export function segmentar(texto: string, termos: TermoGlossario[]): Trecho[] {
  const formas: { forma: string; termo: TermoGlossario }[] = [];
  for (const termo of termos) for (const forma of termo.formas) formas.push({ forma, termo });
  formas.sort((x, y) => y.forma.length - x.forma.length);

  const ocupado: [number, number][] = [];
  const achados: { i: number; f: number; termo: TermoGlossario }[] = [];
  for (const { forma, termo } of formas) {
    // Siglas só casam em maiúsculas; o resto ignora caixa e aceita plural, como no servidor.
    const re = new RegExp(`(?<!${LETRA})${escapar(forma)}${ehSigla(forma) ? "" : "(?:s|es)?"}(?!${LETRA})`, ehSigla(forma) ? "g" : "gi");
    for (const m of texto.matchAll(re)) {
      const i = m.index ?? 0, f = i + m[0].length;
      if (ocupado.some(([a, b]) => i < b && a < f)) continue;
      ocupado.push([i, f]);
      achados.push({ i, f, termo });
    }
  }
  achados.sort((x, y) => x.i - y.i);

  const saida: Trecho[] = [];
  let pos = 0;
  for (const a of achados) {
    if (a.i > pos) saida.push({ texto: texto.slice(pos, a.i) });
    saida.push({ texto: texto.slice(a.i, a.f), termo: a.termo });
    pos = a.f;
  }
  if (pos < texto.length) saida.push({ texto: texto.slice(pos) });
  return saida.length ? saida : [{ texto }];
}
