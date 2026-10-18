import { CARACTERES, LARGURA_NEGRITO, LARGURA_NORMAL, MAIS_LARGO_NEGRITO, MAIS_LARGO_NORMAL } from "./medidas";

/** Encaixa texto numa caixa medindo a Arial de verdade (tabela em medidas.ts), sem depender de navegador.
 * Garantia: toda linha devolvida mede no máximo a largura pedida, e as linhas cabem na altura. */

const INDICE = new Map([...CARACTERES].map((c, i) => [c, i]));
const FOLGA = 1.03;          // 3% a mais em cada medida: kerning e arredondamento do renderizador nunca estouram a caixa

export interface Caixa { x: number; y: number; largura: number; altura: number }

/** Largura do texto em pixels, numa fonte de `tamanho` px. Caractere fora da tabela conta como o mais largo. */
export function medir(texto: string, tamanho: number, negrito = false): number {
  const tabela = negrito ? LARGURA_NEGRITO : LARGURA_NORMAL;
  const maior = negrito ? MAIS_LARGO_NEGRITO : MAIS_LARGO_NORMAL;
  let milesimos = 0;
  for (const c of texto) {
    const i = INDICE.get(c);
    milesimos += i === undefined ? maior : tabela[i];
  }
  return (milesimos / 1000) * tamanho * FOLGA;
}

/** Quebra em linhas que cabem em `largura`. Palavra maior que a linha é partida em pedaços que cabem. */
export function quebrar(texto: string, largura: number, tamanho: number, negrito = false): string[] {
  const linhas: string[] = [];
  let atual = "";
  for (const bruta of texto.split(/\s+/).filter(Boolean)) {
    for (const palavra of partir(bruta, largura, tamanho, negrito)) {
      const junto = atual ? `${atual} ${palavra}` : palavra;
      if (atual && medir(junto, tamanho, negrito) > largura) { linhas.push(atual); atual = palavra; }
      else atual = junto;
    }
  }
  if (atual) linhas.push(atual);
  return linhas;
}

function partir(palavra: string, largura: number, tamanho: number, negrito: boolean): string[] {
  if (medir(palavra, tamanho, negrito) <= largura) return [palavra];
  const pedacos: string[] = [];
  let atual = "";
  for (const c of palavra) {
    if (atual && medir(atual + c, tamanho, negrito) > largura) { pedacos.push(atual); atual = c; }
    else atual += c;
  }
  if (atual) pedacos.push(atual);
  return pedacos;
}

/** Corta com reticências para caber numa linha só (rótulos de gráfico). */
export function cortar(texto: string, largura: number, tamanho: number, negrito = false): string {
  if (medir(texto, tamanho, negrito) <= largura) return texto;
  let s = [...texto];
  while (s.length > 0 && medir(`${s.join("").trimEnd()}…`, tamanho, negrito) > largura) s = s.slice(0, -1);
  return s.length ? `${s.join("").trimEnd()}…` : "";
}

export interface Encaixe { tamanho: number; alturaLinha: number; linhas: string[]; altura: number; largura: number }

export interface Opcoes {
  largura: number; altura: number; tamanhoMax: number; tamanhoMin: number;
  negrito?: boolean; entrelinha?: number; maxLinhas?: number;
}

/** Maior fonte (de tamanhoMax a tamanhoMin) em que o texto cabe na caixa. Se nem no mínimo couber, continua diminuindo
 * até 10 px e, em último caso, corta a última linha com reticências: nunca devolve algo maior que a caixa. */
export function caber(texto: string, o: Opcoes): Encaixe {
  const entrelinha = o.entrelinha ?? 1.25;
  const negrito = o.negrito ?? false;
  const tenta = (t: number): Encaixe => {
    const linhas = quebrar(texto, o.largura, t, negrito);
    const alturaLinha = Math.round(t * entrelinha);
    return { tamanho: t, alturaLinha, linhas, altura: linhas.length * alturaLinha,
      largura: Math.max(0, ...linhas.map((l) => medir(l, t, negrito))) };
  };
  const cabe = (e: Encaixe) => e.altura <= o.altura && (!o.maxLinhas || e.linhas.length <= o.maxLinhas);
  // Desce de 2 em 2. Abaixo de tamanhoMin só em texto fora dos limites do avaliador, que o desenho ainda precisa conter.
  for (let t = o.tamanhoMax; t >= 10; t -= 2) {
    const e = tenta(t);
    if (cabe(e)) return e;
  }
  // Último recurso: fonte mínima e só as linhas que cabem, a última com reticências.
  const e = tenta(10);
  const max = Math.max(1, Math.min(o.maxLinhas ?? Infinity, Math.floor(o.altura / e.alturaLinha)));
  const linhas = e.linhas.slice(0, max);
  if (e.linhas.length > max) linhas[max - 1] = cortar(`${linhas[max - 1]} ${e.linhas[max]}`, o.largura, 10, negrito);
  return { ...e, linhas, altura: linhas.length * e.alturaLinha, largura: Math.max(0, ...linhas.map((l) => medir(l, 10, negrito))) };
}

/** Linhas de texto em SVG, a partir do topo `y`: a primeira linha de base fica a 0,93 em do topo (ascendente da Arial)
 * e a descendente da última termina dentro de `altura`. */
export function linhasSvg(e: Encaixe, x: number, y: number, atributos: string, ancora: "start" | "middle" = "start"): string {
  const tspans = e.linhas.map((l, i) => `<tspan x="${x}" y="${Math.round(y + e.tamanho * 0.93 + i * e.alturaLinha)}">${xml(l)}</tspan>`).join("");
  return `<text font-family="Arial, Helvetica, sans-serif" font-size="${e.tamanho}" text-anchor="${ancora}" ${atributos}>${tspans}</text>`;
}

export const xml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
