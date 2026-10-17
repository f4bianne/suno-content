import { ROTULO_NIVEL, type Nivel, type Tentativa } from "../tipos";

/** Um problema de um conteúdo reprovado, em linguagem de quem lê, com o que mudar no texto. */
export interface Diagnostico { problema: string; sugestao: string; tecnico?: boolean }

/** As mensagens do servidor juntam o problema e uma instrução para o modelo ("Responda no schema", "Não calcule").
 * Aqui cada regra vira uma frase para a pessoa, aproveitando o que a mensagem traz: o termo, a definição, os fatos. */
export function diagnosticar(falha: string, nivel: Nivel): Diagnostico {
  const etiqueta = /^\[(\w+)\]/.exec(falha)?.[1] ?? "";
  const msg = falha.replace(/^\[[^\]]+\]\s*/, "");
  const nomeNivel = ROTULO_NIVEL[nivel];
  let m: RegExpExecArray | null;

  if (/não foi possível avaliar|não obedeceu ao formato pedido \(\w+:/.test(msg)) {
    return { tecnico: true, problema: "Falha técnica: o serviço do modelo não respondeu a tempo ou recusou o pedido.",
      sugestao: "Não é um problema do texto. Gerar de novo mais tarde costuma resolver." };
  }

  switch (etiqueta) {
    case "glossario":
      if ((m = /termo de nível 3 proibido: '([^']+)'/.exec(msg))) {
        const def = definicao(msg, m[1]);
        return { problema: `“${m[1]}” é jargão de especialista e não pode aparecer no nível ${nomeNivel}.`,
          sugestao: def ? `Diga com palavras simples, por exemplo: “${def}”.` : "Diga a mesma ideia com palavras do dia a dia." };
      }
      if ((m = /termo de nível \d sem explica\S+: '([^']+)' em "(.*?)"/.exec(msg))) {
        const def = definicao(msg, m[1]);
        return { problema: `“${m[1]}” aparece sem explicação, e o leitor do nível ${nomeNivel} pode não conhecer (${m[2]}).`,
          sugestao: def ? `Explique na primeira vez em que aparece: “${m[1]}, que é ${def}”. Ou troque por palavras simples.`
            : "Explique na mesma frase, com “ou seja” ou “que é”, ou troque por palavras simples." };
      }
      if ((m = /densidade de termos nível 2-3 ([\d.]+) abaixo de ([\d.]+)/.exec(msg))) {
        return { problema: `Pouco vocabulário técnico para o nível ${nomeNivel}: ${br(m[1])} termos de mercado por 100 palavras (mínimo ${br(m[2])}).`,
          sugestao: "Use os termos técnicos do próprio documento, como num relatório para especialistas." };
      }
      break;
    case "legibilidade":
      if ((m = /Flesch ([\d.]+) fora da faixa (\d+) a (\d+)/.exec(msg))) {
        const [v, lo, hi] = [Number(m[1]), Number(m[2]), Number(m[3])];
        return v > hi
          ? { problema: `Texto simples demais para o nível ${nomeNivel}: índice de leitura ${br(m[1])}, esperado de ${lo} a ${hi}.`,
              sugestao: "Use frases mais longas e encadeadas, com o vocabulário técnico do documento." }
          : { problema: `Texto difícil demais para o nível ${nomeNivel}: índice de leitura ${br(m[1])}, esperado de ${lo} a ${hi}.`,
              sugestao: "Encurte as frases (uma ideia por frase) e troque palavras longas por palavras do dia a dia." };
      }
      break;
    case "cobertura":
      if ((m = /cobertura (\d+)% abaixo de (\d+)%/.exec(msg))) {
        const fatos = [...msg.matchAll(/\[f\d+\]\s*([^[]+?)(?=\s*\[f\d+\]|$)/g)]
          // Cada fato termina na primeira frase: depois dela o servidor costuma emendar uma instrução para o modelo.
          .map((x) => x[1].split(/\.\s/)[0].replace(/[.;\s]+$/, "").trim());
        return { problema: `Faltaram fatos importantes do documento: o texto cobre ${m[1]}% deles, e o mínimo é ${m[2]}%.`,
          sugestao: fatos.length ? `Inclua, com os números exatos: ${fatos.map((f) => `“${f}”`).join("; ")}.`
            : "Inclua os fatos que ficaram de fora, com os números exatos do documento." };
      }
      break;
    case "numeros":
      if ((m = /número '([^']+)'/.exec(msg))) {
        return { problema: `O número ${m[1]} não está no documento${msg.startsWith("gráfico") ? " (aparece no gráfico)" : ""}.`,
          sugestao: "Remova ou use o número exato do documento, sem calcular, somar ou arredondar." };
      }
      break;
    case "recomendacao":
      return { problema: `Soa como conselho de investimento: ${msg.replace(/^linguagem de recomendação:\s*/, "")}.`,
        sugestao: "Descreva o que o documento diz e o que isso significa, sem dizer ao leitor para comprar, vender ou aplicar." };
    case "formato":
    case "duracao":
      if ((m = /artigo com (\d+) palavras \(esperado de (\d+) a (\d+)\)/.exec(msg))) {
        const curto = Number(m[1]) < Number(m[2]);
        return { problema: `O artigo tem ${m[1]} palavras; o esperado é de ${m[2]} a ${m[3]}.`,
          sugestao: curto ? "Desenvolva cada fato com contexto e consequências, sem acrescentar números." : "Corte o que for menos importante." };
      }
      if ((m = /carrossel com (\d+) slides \(esperado de (\d+) a (\d+)\)/.exec(msg))) {
        const poucos = Number(m[1]) < Number(m[2]);
        return { problema: `O carrossel tem ${m[1]} slides; o esperado é de ${m[2]} a ${m[3]}.`,
          sugestao: poucos ? "Divida as ideias em mais slides, uma por slide." : "Junte slides parecidos ou corte os menos importantes." };
      }
      if ((m = /slide (\d+) com (\d+) caracteres \(máximo (\d+)\)/.exec(msg))) {
        return { problema: `O slide ${m[1]} tem ${m[2]} caracteres; o máximo é ${m[3]}.`,
          sugestao: `Corte pelo menos ${Number(m[2]) - Number(m[3])} caracteres desse slide, tirando o que for menos importante.` };
      }
      if ((m = /(?:fala de \d+ palavras leva (?:cerca de )?|roteiro marca )(\d+)s(?: \(máximo (\d+)s\))?/.exec(msg))) {
        return { problema: `O vídeo passa do tempo: cerca de ${m[1]} s de fala, e o máximo é ${m[2] ?? 60} s.`,
          sugestao: "Corte a cena ou a frase menos importante, em vez de acelerar a fala." };
      }
      break;
    case "juiz":
      if ((m = /afirmação sem suporte nos fatos[^:]*:\s*(.+)/.exec(msg))) {
        return { problema: `O juiz não achou base no documento para: “${m[1].trim()}”`,
          sugestao: "Remova a frase ou reescreva usando só o que o documento afirma." };
      }
      if ((m = /critério do nível não atendido:\s*(.+)/.exec(msg))) {
        const [criterio, ...resto] = frases(m[1]);
        return { problema: `Faltou um critério do nível ${nomeNivel}: ${criterio}`,
          sugestao: resto.join(" ") || "Ajuste o texto para atender esse critério, sem acrescentar fatos." };
      }
      if ((m = /fato ausente:\s*(\S+)/.exec(msg))) {
        return { problema: `O juiz notou que um fato do documento (${m[1]}) ficou de fora.`,
          sugestao: "Inclua esse fato, com os números exatos. A lista está em “Fatos e fonte do documento”." };
      }
      if ((m = /notas baixas \(fidelidade (\d), nível (\d)\)/.exec(msg))) {
        const fiel = Number(m[1]) >= 4;
        return { problema: `O juiz deu notas baixas: fidelidade ${m[1]}/5 e adequação ao nível ${m[2]}/5.`,
          sugestao: fiel ? `Ajuste o vocabulário e o foco ao leitor do nível ${nomeNivel}.` : "Fique só no que o documento afirma, sem interpretar além dele." };
      }
      break;
  }
  const [primeira, ...resto] = frases(msg);
  return { problema: primeira, sugestao: resto.join(" ") || "Revise o trecho apontado." };
}

/** Todos os problemas da versão final, os que bloqueiam primeiro, sem repetir a mesma frase. */
export function diagnosticos(t: Tentativa, nivel: Nivel): Diagnostico[] {
  const bloqueios = new Set(t.metricas.nota?.bloqueios ?? []);
  const etiqueta = (f: string) => /^\[(\w+)\]/.exec(f)?.[1] ?? "";
  const pesa = (f: string) => (bloqueios.has(etiqueta(f)) || (etiqueta(f) === "juiz" && bloqueios.has("fidelidade")) ? 0 : 1);
  const vistos = new Set<string>();
  return [...t.falhas].sort((a, b) => pesa(a) - pesa(b)).map((f) => diagnosticar(f, nivel))
    .filter((d) => !vistos.has(d.problema) && vistos.add(d.problema));
}

/** "escreva algo como: Copom, que é comitê do Banco Central que decide a taxa Selic." -> a definição. */
function definicao(msg: string, termo: string): string | null {
  const m = new RegExp(`algo como:\\s*${termo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")},\\s*que é\\s*(.+?)\\.?$`, "i").exec(msg);
  return m ? m[1].trim() : null;
}

const frases = (s: string) => s.split(/(?<=[.!?])\s+/).map((x) => x.trim()).filter(Boolean);
const br = (n: string) => n.replace(".", ",");
