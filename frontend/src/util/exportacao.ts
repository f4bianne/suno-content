import type { Processamento, Ramo } from "../tipos";
import { ROTULO_FORMATO, ROTULO_NIVEL } from "../tipos";
import { MARCA_CLARA, MARCA_ESCURA, MARCA_PROPORCAO } from "./marca";

const TAMANHO = 1080;      // slide quadrado, o formato padrão de carrossel
const ESPACO = 80;         // entre slides na folha
const VERMELHO = "#D42126", CARVAO = "#222222", PRETO = "#131313", CINZA = "#767676", BRANCO = "#FFFFFF";

export const AVISO_IMAGEM =
  "Imagens geradas fora do sistema não passam pelo avaliador: confira se não trazem texto, números ou promessas que o conteúdo aprovado não tem.";

const xml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Quebra o texto em linhas de no máximo `max` caracteres, sem cortar palavras. */
export function quebrarLinhas(texto: string, max: number): string[] {
  const linhas: string[] = [];
  let atual = "";
  for (const palavra of texto.split(/\s+/).filter(Boolean)) {
    if (atual && `${atual} ${palavra}`.length > max) { linhas.push(atual); atual = palavra; }
    else atual = atual ? `${atual} ${palavra}` : palavra;
  }
  if (atual) linhas.push(atual);
  return linhas;
}

type Papel = "gancho" | "corpo" | "conclusao";

const LOGO_ALTURA = 40;

/** A logo oficial embutida (data URI), para o arquivo abrir sozinho e no Figma. `href` e `xlink:href` cobrem SVG 1 e 2. */
function logo(escuro: boolean): string {
  const src = escuro ? MARCA_ESCURA : MARCA_CLARA;
  const largura = Math.round(LOGO_ALTURA * MARCA_PROPORCAO);
  return `<image xmlns:xlink="http://www.w3.org/1999/xlink" x="96" y="${104 - LOGO_ALTURA + 8}" width="${largura}" height="${LOGO_ALTURA}" href="${src}" xlink:href="${src}"><title>Suno</title></image>`;
}

/** Um slide em SVG, com a identidade da Suno: gancho em carvão, corpo em branco, vermelho só no detalhe. */
export function slideSvg(texto: string, indice: number, total: number, deslocamentoX = 0): string {
  const papel: Papel = indice === 0 ? "gancho" : indice === total - 1 ? "conclusao" : "corpo";
  const escuro = papel === "gancho";
  const fundo = escuro ? PRETO : BRANCO, tinta = escuro ? BRANCO : CARVAO, apoio = escuro ? "#A6A6A6" : CINZA;
  const tamanho = papel === "gancho" ? 84 : 60, max = papel === "gancho" ? 20 : 28, altura = Math.round(tamanho * 1.28);
  const linhas = quebrarLinhas(texto, max).slice(0, 9);
  const inicioY = Math.round((TAMANHO - linhas.length * altura) / 2) + tamanho * 0.3;
  const tspans = linhas.map((l, i) => `<tspan x="96" y="${inicioY + i * altura}">${xml(l)}</tspan>`).join("");
  const rotulo = papel === "gancho" ? "GANCHO" : papel === "conclusao" ? "CONCLUSÃO" : `${indice + 1} DE ${total}`;
  return `<g id="slide-${indice + 1}-${papel}" transform="translate(${deslocamentoX},0)">
  <rect width="${TAMANHO}" height="${TAMANHO}" fill="${fundo}"/>
  ${logo(escuro)}
  <text x="${TAMANHO - 96}" y="104" text-anchor="end" font-family="Arial, Helvetica, sans-serif" font-size="26" font-weight="700" letter-spacing="3" fill="${apoio}">${String(indice + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}</text>
  <rect x="96" y="136" width="${TAMANHO - 192}" height="2" fill="${escuro ? "#3A3A3A" : "#D9D9D9"}"/>
  <text font-family="Arial, Helvetica, sans-serif" font-size="${tamanho}" font-weight="${papel === "corpo" ? 400 : 700}" fill="${tinta}">${tspans}</text>
  <rect x="96" y="${TAMANHO - 150}" width="120" height="6" fill="${VERMELHO}"/>
  <text x="96" y="${TAMANHO - 96}" font-family="Arial, Helvetica, sans-serif" font-size="26" font-weight="700" letter-spacing="4" fill="${apoio}">${xml(rotulo)}</text>
</g>`;
}

/** Um slide como arquivo SVG completo, para baixar separado. */
export function slideSvgCompleto(texto: string, indice: number, total: number): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${TAMANHO}" height="${TAMANHO}" viewBox="0 0 ${TAMANHO} ${TAMANHO}">
${slideSvg(texto, indice, total)}
</svg>`;
}

/** Todos os slides lado a lado em um único SVG; no Figma, cada slide chega como um grupo com nome. */
export function folhaSvg(slides: string[]): string {
  const largura = slides.length * TAMANHO + Math.max(0, slides.length - 1) * ESPACO;
  const grupos = slides.map((s, i) => slideSvg(s, i, slides.length, i * (TAMANHO + ESPACO))).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${largura}" height="${TAMANHO}" viewBox="0 0 ${largura} ${TAMANHO}">
<title>Carrossel Suno Content</title>
${grupos}
</svg>`;
}

export const nomeDoArquivo = (r: Pick<Processamento, "origem">, ramo: Pick<Ramo, "nivel" | "formato">, ext: string): string => {
  const base = `${r.origem}-${ramo.nivel}-${ramo.formato}`.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${base.toLowerCase()}.${ext}`;
};

const ESTILO = "Ilustração editorial minimalista e sóbria, fundo carvão e branco, um único detalhe em vermelho (#D42126), " +
  "formas geométricas simples, sem pessoas reconhecíveis, sem logotipos, sem qualquer texto ou número escrito na imagem";

/** Prompt para uma IA de imagem, um item por slide do carrossel. Só vale para carrossel; nos outros formatos devolve vazio. */
export function promptImagem(r: Processamento, ramo: Ramo): string {
  const c = ramo.conteudo;
  if (!c || !("slides" in c)) return "";
  const cabecalho = `Conteúdo: ${ROTULO_NIVEL[ramo.nivel]}, ${ROTULO_FORMATO[ramo.formato]}, sobre "${r.origem}".\nEstilo para todas as imagens: ${ESTILO}.\n`;
  const itens = c.slides.map((s, i) => `Imagem ${i + 1} (quadrada, 1080x1080) para o slide: "${s}"`);
  return `${cabecalho}\n${itens.join("\n")}\n\n${AVISO_IMAGEM}`;
}

/** Baixa um texto como arquivo. Separado para poder ser trocado nos testes. */
export function baixar(nome: string, conteudo: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([conteudo], { type: mime }));
  const a = document.createElement("a");
  a.href = url; a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
