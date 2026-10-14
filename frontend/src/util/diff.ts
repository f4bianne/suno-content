export type TipoParte = "igual" | "removido" | "adicionado";
export interface Parte { tipo: TipoParte; texto: string }

/** Diferença palavra a palavra (maior subsequência comum). Textos muito longos caem para parágrafos. */
export function diferenca(antes: string, depois: string): Parte[] {
  let a = antes.split(/\s+/).filter(Boolean);
  let b = depois.split(/\s+/).filter(Boolean);
  if (a.length * b.length > 250_000) {   // evita travar a tela em textos enormes
    a = antes.split(/\n+/).filter(Boolean);
    b = depois.split(/\n+/).filter(Boolean);
  }
  const n = a.length, m = b.length;
  const t: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--) t[i][j] = a[i] === b[j] ? t[i + 1][j + 1] + 1 : Math.max(t[i + 1][j], t[i][j + 1]);

  const partes: Parte[] = [];
  const empilha = (tipo: TipoParte, texto: string) => {
    const ultima = partes[partes.length - 1];
    if (ultima && ultima.tipo === tipo) ultima.texto += ` ${texto}`;
    else partes.push({ tipo, texto });
  };
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { empilha("igual", a[i]); i++; j++; }
    else if (t[i + 1][j] >= t[i][j + 1]) { empilha("removido", a[i]); i++; }
    else { empilha("adicionado", b[j]); j++; }
  }
  while (i < n) empilha("removido", a[i++]);
  while (j < m) empilha("adicionado", b[j++]);
  return partes;
}

/** Quanto do texto mudou, de 0 a 1. */
export function proporcaoAlterada(partes: Parte[]): number {
  const palavras = (p: Parte) => p.texto.split(/\s+/).length;
  const total = partes.reduce((s, p) => s + palavras(p), 0);
  const mudou = partes.filter((p) => p.tipo !== "igual").reduce((s, p) => s + palavras(p), 0);
  return total ? mudou / total : 0;
}
