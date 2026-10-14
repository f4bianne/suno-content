import type { Processamento, Ramo } from "../tipos";
import { ROTULO_NIVEL } from "../tipos";
import { dataBr } from "./conteudo";

export interface TextoArtigo { titulo: string; corpo: string; conclusao: string }

const paragrafos = (t: string) => t.split(/\n{1,}/).map((p) => p.trim()).filter(Boolean);
const escapar = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Fonte e data no rodapé: o texto sempre leva consigo de onde veio. */
function fonte(r: Pick<Processamento, "origem" | "url" | "gerado_em">, ramo: Pick<Ramo, "nivel">): string {
  return `Fonte: ${r.origem}${r.url ? ` (${r.url})` : ""}. Nível ${ROTULO_NIVEL[ramo.nivel]}. Gerado em ${dataBr(r.gerado_em)}.`;
}

/** Texto limpo, para colar em qualquer editor ou e-mail. */
export function artigoEmTexto(a: TextoArtigo, r: Processamento, ramo: Ramo): string {
  return [a.titulo.toUpperCase(), "", ...paragrafos(a.corpo).flatMap((p) => [p, ""]), a.conclusao.trim(), "", "—", fonte(r, ramo), ""].join("\n");
}

/** Markdown, para blogs, wikis e ferramentas de newsletter. */
export function artigoEmMarkdown(a: TextoArtigo, r: Processamento, ramo: Ramo): string {
  return [`# ${a.titulo}`, "", ...paragrafos(a.corpo).flatMap((p) => [p, ""]), a.conclusao.trim(), "", "---", `*${fonte(r, ramo)}*`, ""].join("\n");
}

/** HTML simples e limpo, pronto para colar no gerenciador de conteúdo do site ou da newsletter. */
export function artigoEmHtml(a: TextoArtigo, r: Processamento, ramo: Ramo): string {
  const corpo = paragrafos(a.corpo).map((p) => `  <p>${escapar(p)}</p>`).join("\n");
  return `<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>${escapar(a.titulo)}</title>
</head>
<body>
<article>
  <h1>${escapar(a.titulo)}</h1>
${corpo}
  <p>${escapar(a.conclusao.trim())}</p>
  <footer><small>${escapar(fonte(r, ramo))}</small></footer>
</article>
</body>
</html>
`;
}
