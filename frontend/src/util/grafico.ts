import type { Grafico } from "../tipos";
import { caber, cortar, linhasSvg, medir, xml, type Caixa } from "./caber";

/** Cores do gráfico. Na exportação são hexadecimais; na tela, variáveis CSS (por isso vão em `style`, não em `fill`). */
export interface Cores { tinta: string; apoio: string; grade: string; destaque: string }

export interface Desenho { svg: string; ocupado: Caixa[] }

/** 4.9 -> "4,9"; 5216 -> "5.216": o mesmo jeito que os fatos escrevem (igual a numero_br no servidor). */
export function numeroBr(v: number): string {
  const [inteiro, decimais] = Math.abs(v).toFixed(2).split(".");
  const milhar = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const resto = decimais.replace(/0+$/, "");
  const s = resto ? `${milhar},${resto}` : milhar;
  return v < 0 && s !== "0" ? `-${s}` : s;
}

const FONTE = `font-family="Arial, Helvetica, sans-serif"`;

/** Desenha o gráfico dentro de `caixa`. Cada texto é medido e encaixado (fonte menor ou reticências) e cada forma é
 * calculada a partir da caixa, então nada sai dela. `ocupado` lista a área de cada elemento, para os testes conferirem. */
export function desenharGrafico(g: Grafico, caixa: Caixa, cores: Cores): Desenho {
  const { x, y, largura, altura } = caixa;
  const ocupado: Caixa[] = [];
  const partes: string[] = [];
  const n = Math.max(1, g.valores.length);

  // Título: até 2 linhas, em cima.
  const titulo = caber(g.titulo, { largura, altura: Math.min(96, altura * 0.25), tamanhoMax: 34, tamanhoMin: 20, negrito: true, maxLinhas: 2 });
  partes.push(linhasSvg(titulo, x, y, `font-weight="700" style="fill:${cores.tinta}"`));
  ocupado.push({ x, y, largura: titulo.largura, altura: titulo.altura });
  const topo = y + titulo.altura + 20;

  // Rótulos embaixo e valores sobre os pontos: um tamanho para todos, o maior em que o mais largo cabe na sua faixa.
  const faixa = largura / n;
  const textosValor = g.valores.map((v) => `${numeroBr(v)}${g.unidade}`);
  const tamanhoQueCabe = (textos: string[], max: number, negrito: boolean) => {
    for (let t = max; t > 14; t -= 1) if (textos.every((s) => medir(s, t, negrito) <= faixa - 8)) return t;
    return 14;
  };
  const tRotulo = tamanhoQueCabe(g.rotulos, 26, false);
  const tValor = tamanhoQueCabe(textosValor, 28, true);
  const rotulos = g.rotulos.map((r) => cortar(r, faixa - 8, tRotulo));
  const valores = textosValor.map((s) => cortar(s, faixa - 8, tValor, true));
  const altRotulo = Math.round(tRotulo * 1.25), altValor = Math.round(tValor * 1.25);

  const base = y + altura - altRotulo - 12;                   // fim da área do desenho
  // Rótulo de valor embaixo: barra negativa, ou ponto da linha num vale (a linha chega por cima e cobriria o texto).
  const embaixo = g.valores.map((v, i) => g.tipo === "barras" ? v < 0
    : (i > 0 && g.valores[i - 1] > v) && (i === g.valores.length - 1 || g.valores[i + 1] >= v));
  const areaTopo = topo + altValor + 6 + (g.tipo === "linha" ? 10 : 0);
  const areaFim = base - (embaixo.some(Boolean) ? altValor + 16 : 0);
  const areaAltura = Math.max(10, areaFim - areaTopo);

  // Escala: barras sempre a partir do zero; linha com folga de 10% em volta dos valores.
  const finitos = g.valores.filter(Number.isFinite);
  let lo = Math.min(...finitos), hi = Math.max(...finitos);
  if (!finitos.length) { lo = 0; hi = 1; }
  if (g.tipo === "barras") { lo = Math.min(0, lo); hi = Math.max(0, hi); }
  else { const folga = (hi - lo) * 0.1 || Math.abs(hi) * 0.1 || 1; lo -= folga; hi += folga; }
  if (hi === lo) hi = lo + 1;
  const yDe = (v: number) => areaTopo + ((hi - Math.min(hi, Math.max(lo, v))) / (hi - lo)) * areaAltura;
  const centro = (i: number) => x + faixa * i + faixa / 2;

  const zero = g.tipo === "barras" ? yDe(0) : areaFim;
  partes.push(`<rect x="${x}" y="${Math.round(zero)}" width="${largura}" height="2" style="fill:${cores.grade}"/>`);

  if (g.tipo === "barras") {
    const larguraBarra = Math.min(faixa * 0.6, 160);
    g.valores.forEach((v, i) => {
      const yv = yDe(Number.isFinite(v) ? v : 0);
      const topoBarra = Math.min(yv, zero), alturaBarra = Math.max(2, Math.abs(zero - yv));
      const bx = centro(i) - larguraBarra / 2;
      partes.push(`<rect x="${Math.round(bx)}" y="${Math.round(topoBarra)}" width="${Math.round(larguraBarra)}" height="${Math.round(alturaBarra)}" rx="4" style="fill:${cores.destaque}"/>`);
      ocupado.push({ x: bx, y: topoBarra, largura: larguraBarra, altura: alturaBarra });
      const yTexto = v < 0 ? topoBarra + alturaBarra + 6 : topoBarra - altValor - 6;
      partes.push(valorSvg(valores[i], centro(i), yTexto, tValor, cores.tinta));
      ocupado.push(caixaCentrada(valores[i], centro(i), yTexto, tValor, altValor, true));
    });
  } else {
    const pontos = g.valores.map((v, i) => [centro(i), yDe(Number.isFinite(v) ? v : 0)] as const);
    partes.push(`<polyline points="${pontos.map(([px, py]) => `${Math.round(px)},${Math.round(py)}`).join(" ")}" style="fill:none;stroke:${cores.destaque};stroke-width:6;stroke-linejoin:round;stroke-linecap:round"/>`);
    pontos.forEach(([px, py], i) => {
      partes.push(`<circle cx="${Math.round(px)}" cy="${Math.round(py)}" r="9" style="fill:${cores.destaque}"/>`);
      ocupado.push({ x: px - 9, y: py - 9, largura: 18, altura: 18 });
      const yTexto = embaixo[i] ? py + 16 : py - altValor - 10;
      partes.push(valorSvg(valores[i], px, yTexto, tValor, cores.tinta));
      ocupado.push(caixaCentrada(valores[i], px, yTexto, tValor, altValor, true));
    });
  }

  rotulos.forEach((r, i) => {
    const yTexto = base + 12;
    partes.push(`<text ${FONTE} font-size="${tRotulo}" text-anchor="middle" x="${Math.round(centro(i))}" y="${Math.round(yTexto + tRotulo * 0.93)}" style="fill:${cores.apoio}">${xml(r)}</text>`);
    ocupado.push(caixaCentrada(r, centro(i), yTexto, tRotulo, altRotulo, false));
  });

  return { svg: `<g class="grafico">${partes.join("")}</g>`, ocupado };
}

function valorSvg(texto: string, cx: number, topo: number, tamanho: number, cor: string): string {
  return `<text ${FONTE} font-size="${tamanho}" font-weight="700" text-anchor="middle" x="${Math.round(cx)}" y="${Math.round(topo + tamanho * 0.93)}" style="fill:${cor}">${xml(texto)}</text>`;
}

function caixaCentrada(texto: string, cx: number, topo: number, tamanho: number, altura: number, negrito: boolean): Caixa {
  const l = medir(texto, tamanho, negrito);
  return { x: cx - l / 2, y: topo, largura: l, altura };
}
