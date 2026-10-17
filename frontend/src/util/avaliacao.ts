import type { Config, Ramo, Tentativa } from "../tipos";

/** "ok" passou; "aviso" teve problema, mas a nota do texto alcançou o limiar; "falhou" reprovou; "nao_rodou" não
 * chegou a ser avaliado (o juiz não é chamado quando as regras já deixam a nota abaixo do mínimo). */
export type Estado = "ok" | "aviso" | "falhou" | "nao_rodou";

/** Nota de 0 a 1 em formato brasileiro: 0,91. */
export const nota = (v: number) => v.toFixed(2).replace(".", ",");
export interface Checagem { id: string; titulo: string; detalhe: string; estado: Estado; motivo?: string }

const limitar = (v: number) => Math.max(0, Math.min(100, v));

/** As falhas do servidor começam com a etiqueta da regra, por exemplo "[glossario] termo de nível 3 ...". */
export function falhasDaRegra(t: Tentativa, ...etiquetas: string[]): string[] {
  return t.falhas
    .filter((f) => etiquetas.some((e) => f.startsWith(`[${e}]`)))
    .map((f) => f.replace(/^\[[^\]]+\]\s*/, ""));
}

/** Primeira frase da mensagem, com tamanho limitado: o suficiente para entender sem virar um parágrafo. */
export function resumir(msg: string, max = 150): string {
  const primeira = msg.split(/(?<=[.;])\s/)[0] ?? msg;
  return primeira.length > max ? `${primeira.slice(0, max - 1)}…` : primeira;
}

export function faixaFlesch(config: Config | null, ramo: Pick<Ramo, "nivel" | "formato">): [number, number] | null {
  const l = config?.limiares[ramo.nivel];
  if (!l) return null;
  return (ramo.formato === "video" && l.flesch_video) || (ramo.formato === "carrossel" && l.flesch_carrossel) || l.flesch;
}

/** Traduz as métricas técnicas em perguntas simples de sim ou não. */
export function checagens(t: Tentativa, ramo: Pick<Ramo, "nivel" | "formato">, config: Config | null): Checagem[] {
  const faixa = faixaFlesch(config, ramo);
  const minimo = config?.limiares[ramo.nivel]?.cobertura_minima;
  const m = t.metricas;
  // Num texto aprovado, um problema leve não reprovou: a nota alcançou o limiar mesmo com ele.
  const comFalha: Estado = t.aprovado ? "aviso" : "falhou";
  const regra = (id: string, titulo: string, detalhe: string, ...etiquetas: string[]): Checagem => {
    const falhas = falhasDaRegra(t, ...etiquetas);
    return { id, titulo, detalhe, estado: falhas.length ? comFalha : "ok", motivo: falhas.length ? resumir(falhas[0]) : undefined };
  };

  const leitura = regra(
    "leitura", "Leitura no nível certo",
    m.flesch !== undefined && faixa ? `Índice de leitura ${m.flesch} (esperado de ${faixa[0]} a ${faixa[1]})` : "Facilidade de leitura do texto",
    "legibilidade",
  );
  const fatos = regra(
    "fatos", "Fiel aos fatos do documento",
    m.cobertura !== undefined ? `${Math.round(m.cobertura * 100)}% dos fatos principais citados${minimo ? ` (mínimo ${Math.round(minimo * 100)}%)` : ""}` : "Fatos e números do documento",
    "cobertura", "numeros",
  );

  const deRegras = [
    leitura,
    regra("termos", "Termos técnicos adequados ao nível", "Jargão permitido para quem vai ler", "glossario"),
    fatos,
    regra("conselho", "Sem conselho de investimento", "Informa, mas não recomenda comprar ou vender", "recomendacao"),
    regra("formato", "Dentro dos limites do formato", "Tamanho, quantidade de slides ou duração", "formato", "duracao"),
  ];
  const algumaFalhou = deRegras.some((c) => c.estado === "falhou");
  const juizNaoChamado = m.nota?.juiz === "nao_chamado";

  let juiz: Checagem;
  const falhasJuiz = falhasDaRegra(t, "juiz");
  if (t.veredito) {
    juiz = {
      id: "juiz", titulo: "Revisão do juiz (outro modelo)",
      detalhe: `Fidelidade ${t.veredito.nota_fidelidade}/5 · adequação ao nível ${t.veredito.nota_adequacao_nivel}/5`,
      estado: falhasJuiz.length ? comFalha : "ok", motivo: falhasJuiz.length ? resumir(falhasJuiz[0]) : undefined,
    };
  } else if (falhasJuiz.length) {
    juiz = { id: "juiz", titulo: "Revisão do juiz (outro modelo)", detalhe: "O juiz não conseguiu avaliar", estado: "falhou", motivo: resumir(falhasJuiz[0]) };
  } else {
    const naoRodou = juizNaoChamado || (!m.nota && algumaFalhou);   // versões antigas, sem nota: o juiz só rodava sem falha
    juiz = {
      id: "juiz", titulo: "Revisão do juiz (outro modelo)",
      detalhe: naoRodou ? "Não foi chamado: as regras já deixaram a nota abaixo do mínimo" : "Revisão de fidelidade e de nível",
      estado: naoRodou ? "nao_rodou" : "ok",
    };
  }
  return [...deRegras, juiz];
}

/** Nota o Flesch dentro da escala 0 a 100, como o avaliador do servidor faz. */
export function fleschNaFaixa(flesch: number, faixa: [number, number]): boolean {
  const v = limitar(flesch);
  return v >= faixa[0] && v <= faixa[1];
}
