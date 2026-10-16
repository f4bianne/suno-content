export const NIVEIS = ["iniciante", "intermediario", "avancado"] as const;
export const FORMATOS = ["artigo", "carrossel", "video"] as const;
export type Nivel = (typeof NIVEIS)[number];
export type Formato = (typeof FORMATOS)[number];

export const ROTULO_NIVEL: Record<Nivel, string> = { iniciante: "Iniciante", intermediario: "Intermediário", avancado: "Avançado" };
export const ROTULO_FORMATO: Record<Formato, string> = { artigo: "Artigo", carrossel: "Carrossel", video: "Vídeo curto" };

export interface Fato { id: string; texto: string; numeros: string[]; entidades: string[]; trecho_origem: string }
export interface Cena { inicio_s: number; fim_s: number; fala: string; visual: string }
export type Conteudo = { titulo: string; corpo: string; conclusao: string } | { slides: string[] } | { cenas: Cena[] };

export interface Veredito {
  afirmacoes_sem_suporte: string[]; nota_fidelidade: number; criterios_atendidos: string[]; criterios_nao_atendidos: string[];
  nota_adequacao_nivel: number; fatos_confirmados: string[]; fatos_ausentes: string[]; justificativa: string;
}
export interface Metricas {
  flesch?: number; cobertura?: number; fatos_ausentes?: string[];
  densidade?: { contagem: Record<string, number>; nivel23_por_100_palavras: number };
  plano_revisao?: PlanoRevisao;
  explicacoes_inseridas?: string[];   // termos em que o sistema acrescentou a definição do glossário
}
/** O que o agente revisor orientou para a tentativa seguinte. */
export interface PlanoRevisao { diagnostico: string; acoes: string[]; manter: string[] }
export interface Tentativa {
  n: number; aprovado: boolean; falhas: string[]; metricas: Metricas; veredito: Veredito | null; conteudo: Conteudo | null;
  segundos_geracao: number; segundos_avaliacao: number; chamadas_llm: number;
}
export interface Ramo { nivel: Nivel; formato: Formato; status: "aprovado" | "bloqueado"; conteudo: Conteudo | null; tentativas: Tentativa[] }
export interface Processamento {
  gerado_em: string | null; execucao_id: string | null; do_cache: boolean; config: { modelos?: Record<string, string> };
  documento_chave: string; origem: string; url: string | null;
  ancora: { fatos: Fato[] }; fatos_descartados: [string, string][]; ramos: Ramo[];
}

export interface Evento {
  tipo: string; t: number; nivel?: Nivel; formato?: Formato; tentativa?: number; aprovado?: boolean; falhas?: string[];
  flesch?: number | null; status?: string; tentativas?: number; fatos?: number; descartados?: number;
  palavras?: number; paginas?: number | null; mensagem?: string; execucao?: string;
}
export interface Job {
  id: string; status: "ingerindo" | "processando" | "concluido" | "erro"; erro: string | null; eventos: Evento[];
  resultado: Processamento | null; entrada: { tipo: string; valor: string };
}
export interface ResumoExecucao {
  id: string; documento: string; origem: string; url: string | null; tipo: string; escopo: string; criado_em: string; ramos: number; aprovados: number;
}
export interface Config {
  niveis: Nivel[]; formatos: Formato[];
  limiares: Record<Nivel, { flesch: [number, number]; flesch_video?: [number, number]; cobertura_minima: number }>;
}
export interface Relacionado {
  id: string; origem: string; criado_em: string; ramos: number; aprovados: number; entidades_comuns: string[]; afinidade: number;
}
export interface TermoGlossario { termo: string; nivel: number; formas: string[]; explicacao: string; ambiguo: boolean }

/** Estado de um dos 9 conteúdos enquanto o servidor trabalha. */
export type EstadoCelula = { fase: "gerando" | "avaliado" | "revisando" | "fim"; tentativa: number; aprovado?: boolean; status?: string };
