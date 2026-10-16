import type { Config, Processamento, Ramo, Tentativa, TermoGlossario } from "./tipos";

export const config = {
  niveis: ["iniciante", "intermediario", "avancado"], formatos: ["artigo", "carrossel", "video"],
  limiares: {
    iniciante: { flesch: [60, 100], cobertura_minima: 0.8 },
    intermediario: { flesch: [40, 60], cobertura_minima: 0.8 },
    avancado: { flesch: [0, 50], flesch_video: [0, 60], cobertura_minima: 0.9 },
  },
} as unknown as Config;

export const glossario: TermoGlossario[] = [
  { termo: "Selic", nivel: 2, formas: ["Selic", "taxa Selic"], explicacao: "taxa básica de juros da economia", ambiguo: false },
  { termo: "hiato do produto", nivel: 3, formas: ["hiato do produto"], explicacao: "folga da economia", ambiguo: false },
  { termo: "juros", nivel: 1, formas: ["juros"], explicacao: "preço do dinheiro", ambiguo: false },
  { termo: "principal", nivel: 2, formas: ["principal"], explicacao: "valor da dívida", ambiguo: true },
];

const veredito = {
  afirmacoes_sem_suporte: [], nota_fidelidade: 5, criterios_atendidos: [], criterios_nao_atendidos: [], nota_adequacao_nivel: 4,
  fatos_confirmados: [], fatos_ausentes: [], justificativa: "ok",
};
const t = (n: number, falhas: string[], conteudo: Tentativa["conteudo"], extra: Partial<Tentativa> = {}): Tentativa => ({
  n, aprovado: falhas.length === 0, falhas, metricas: { flesch: 72.4, cobertura: 0.93, densidade: { contagem: { "2": 1, "3": 0 }, nivel23_por_100_palavras: 1.2 } },
  veredito: null, conteudo, segundos_geracao: 2, segundos_avaliacao: 3, chamadas_llm: 2, ...extra,
});

const artigoRuim = { titulo: "Juros sobem", corpo: "O hiato do produto negativo pesou sobre a Selic em 14,25%.", conclusao: "Fim." };
const artigoBom = { titulo: "Juros sobem", corpo: "A Selic, que é a taxa básica de juros, subiu para 14,25%. Isso encarece o crédito.", conclusao: "Fique atento." };

function ramo(nivel: Ramo["nivel"], formato: Ramo["formato"], status: Ramo["status"], tentativas: Tentativa[]): Ramo {
  return { nivel, formato, status, conteudo: tentativas[tentativas.length - 1].conteudo, tentativas };
}

const carrossel = { slides: ["Gancho curto", "A Selic subiu para 14,25%", "Isso encarece o crédito", "Fique atento", "Conclusão"] };
const video = { cenas: [
  { inicio_s: 0, fim_s: 20, fala: "A Selic subiu.", visual: "seta para cima" },
  { inicio_s: 20, fim_s: 40, fala: "O crédito fica mais caro.", visual: "casa" },
] };

/** Um resultado completo: o artigo de iniciante foi reescrito e aprovou; o vídeo de iniciante ficou bloqueado. */
export const resultado: Processamento = {
  gerado_em: "2026-10-11T16:29:34Z", execucao_id: "abc123", do_cache: false, config: { modelos: { extrator: "ext", gerador: "gerador-x", juiz: "juiz-y" } },
  documento_chave: "0203078de324aaaa", origem: "Ata do Copom nº 281", url: "https://www.bcb.gov.br/ata.pdf",
  ancora: { fatos: [{ id: "f1", texto: "O Copom elevou a Selic para 14,25%", numeros: ["14,25"], entidades: ["Selic"], trecho_origem: "O Copom elevou a taxa Selic para 14,25% ao ano" }] },
  fatos_descartados: [["trecho de origem não existe no documento", "A Selic vai a 20%"]],
  ramos: [
    ramo("iniciante", "artigo", "aprovado", [
      t(1, ["[glossario] termo de nível 3 proibido: 'hiato do produto' em \"...\". Troque o termo por palavras simples."], artigoRuim),
      t(2, [], artigoBom, { veredito }),
    ]),
    ramo("iniciante", "carrossel", "aprovado", [t(1, [], carrossel, { veredito })]),
    ramo("iniciante", "video", "bloqueado", [
      t(1, ["[formato] roteiro marca 70s (máximo 60s)."], video), t(2, ["[formato] fala de 200 palavras leva 80s."], video),
    ]),
    ramo("intermediario", "artigo", "aprovado", [t(1, [], { ...artigoBom, titulo: "Selic a 14,25%" }, { veredito })]),
    ramo("intermediario", "carrossel", "aprovado", [t(1, [], carrossel, { veredito })]),
    ramo("intermediario", "video", "aprovado", [t(1, [], video, { veredito })]),
    ramo("avancado", "artigo", "aprovado", [t(1, [], { titulo: "Política monetária", corpo: "O hiato do produto e a Selic em 14,25% sustentam a política restritiva.", conclusao: "Cenário aberto." }, { veredito })]),
    ramo("avancado", "carrossel", "aprovado", [t(1, [], carrossel, { veredito })]),
    ramo("avancado", "video", "aprovado", [t(1, [], video, { veredito })]),
  ],
};
