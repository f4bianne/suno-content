import type { Cena } from "../tipos";

/** 65 s vira "1:05". */
export function formatarTempo(s: number): string {
  const total = Math.max(0, Math.round(s));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export const faixaDeTempo = (c: Pick<Cena, "inicio_s" | "fim_s">): string => `${formatarTempo(c.inicio_s)}–${formatarTempo(c.fim_s)}`;

/** Duração total pelo fim da última cena. */
export const duracaoTotal = (cenas: Cena[]): number => cenas.reduce((m, c) => Math.max(m, c.fim_s), 0);

/** Palavras da narração: o que decide se o vídeo cabe no tempo. */
export const palavrasDaFala = (cenas: Cena[]): number => cenas.reduce((n, c) => n + c.fala.split(/\s+/).filter(Boolean).length, 0);

/** Roteiro para ler ou colar em outro lugar, uma cena por bloco. */
export function roteiroEmTexto(titulo: string, cenas: Cena[]): string {
  const blocos = cenas.map((c, i) => [
    `CENA ${i + 1}  |  ${faixaDeTempo(c)}`,
    `NARRAÇÃO: ${c.fala}`,
    `NA TELA: ${c.texto_tela ?? ""}`,
    `AÇÃO E IMAGENS: ${c.visual}`,
  ].join("\n"));
  return [`ROTEIRO: ${titulo}`, `Duração: ${formatarTempo(duracaoTotal(cenas))}`, "", blocos.join("\n\n"), ""].join("\n");
}

const celula = (v: string) => `"${v.replace(/"/g, '""')}"`;

/** Planilha (Excel, Google Planilhas): uma linha por cena. O BOM no início faz o Excel ler os acentos. */
export function roteiroEmCsv(cenas: Cena[]): string {
  const linhas = [
    ["Cena", "Tempo", "Narração", "Texto na tela", "Ação e imagens"],
    ...cenas.map((c, i) => [String(i + 1), faixaDeTempo(c), c.fala, c.texto_tela ?? "", c.visual]),
  ];
  return "﻿" + linhas.map((l) => l.map(celula).join(";")).join("\r\n") + "\r\n";
}

/** Tabela em Markdown, como a que o time de produção costuma usar. */
export function roteiroEmMarkdown(titulo: string, cenas: Cena[]): string {
  const limpa = (v: string) => v.replace(/\|/g, "/").replace(/\s+/g, " ").trim();
  const linhas = cenas.map((c) => `| ${faixaDeTempo(c)} | ${limpa(c.fala)} | ${limpa(c.visual)} | ${limpa(c.texto_tela ?? "")} |`);
  return [
    `# Roteiro: ${titulo}`, "",
    "| Tempo | Narração | Ação e imagens | Texto na tela |", "| --- | --- | --- | --- |",
    ...linhas, "",
  ].join("\n");
}
