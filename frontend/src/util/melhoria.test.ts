import { describe, expect, it } from "vitest";
import type { Tentativa } from "../tipos";
import { diagnosticar, diagnosticos } from "./melhoria";

// Mensagens copiadas do banco, como o servidor as manda.
describe("diagnosticar", () => {
  it("termo proibido vira a troca por palavras simples, com a definição do glossário", () => {
    const d = diagnosticar("[glossario] termo de nível 3 proibido: 'curva de juros futuros' em \"...os juros futuros afetam...\". Troque o termo por palavras simples ou explique-o na mesma frase (\"ou seja\", \"que é\"). Na primeira vez em que usar \"curva de juros futuros\", escreva algo como: curva de juros futuros, que é juros esperados pelo mercado para datas futuras, vistos em contratos de DI.", "iniciante");
    expect(d.problema).toBe("“curva de juros futuros” é jargão de especialista e não pode aparecer no nível Iniciante.");
    expect(d.sugestao).toBe("Diga com palavras simples, por exemplo: “juros esperados pelo mercado para datas futuras, vistos em contratos de DI”.");
  });

  it("termo sem explicação mostra o trecho e a explicação pronta", () => {
    const d = diagnosticar("[glossario] termo de nível 2 sem explicacao: 'Copom' em \"...definida pelo Copom, como a...\". Troque o termo. Na primeira vez em que usar \"Copom\", escreva algo como: Copom, que é comitê do Banco Central que decide a taxa Selic.", "iniciante");
    expect(d.problema).toContain("“Copom” aparece sem explicação");
    expect(d.problema).toContain("definida pelo Copom");
    expect(d.sugestao).toContain("“Copom, que é comitê do Banco Central que decide a taxa Selic”");
  });

  it("legibilidade diz para que lado ajustar", () => {
    expect(diagnosticar("[legibilidade] Flesch 72.8 fora da faixa 0 a 60. Use frases mais longas.", "avancado").problema)
      .toBe("Texto simples demais para o nível Avançado: índice de leitura 72,8, esperado de 0 a 60.");
    expect(diagnosticar("[legibilidade] Flesch 46.6 fora da faixa 60 a 100. Reescreva.", "iniciante").sugestao).toContain("Encurte as frases");
  });

  it("cobertura lista os fatos que faltaram", () => {
    const d = diagnosticar("[cobertura] cobertura 60% abaixo de 80%; ausentes: f2, f4. Inclua estes fatos com seus números: [f2] Houve redução do consumo das famílias. [f4] A Selic ficou em 15%..", "intermediario");
    expect(d.problema).toBe("Faltaram fatos importantes do documento: o texto cobre 60% deles, e o mínimo é 80%.");
    expect(d.sugestao).toBe("Inclua, com os números exatos: “Houve redução do consumo das famílias”; “A Selic ficou em 15%”.");
  });

  it("fato ausente sai sem o ponto e vírgula nem a instrução que o servidor emenda", () => {
    const d = diagnosticar("[cobertura] cobertura 0% abaixo de 80%; ausentes: f1, f2. Inclua: [f1] O ambiente externo segue incerto.; [f2] A dívida pode elevar a taxa neutra.. Cada fato novo entra em uma frase só dele.", "iniciante");
    expect(d.sugestao).toBe("Inclua, com os números exatos: “O ambiente externo segue incerto”; “A dívida pode elevar a taxa neutra”.");
  });

  it("número fora do documento, formato e vídeo longo", () => {
    expect(diagnosticar("[numeros] número '2253' não existe na âncora. Remova ou corrija.", "avancado").problema).toBe("O número 2253 não está no documento.");
    expect(diagnosticar("[formato] slide 3 com 260 caracteres (máximo 220). O slide 3 tem...", "iniciante").sugestao).toContain("pelo menos 40 caracteres");
    expect(diagnosticar("[formato] artigo com 237 palavras (esperado de 250 a 900). Reescreva.", "iniciante").sugestao).toContain("Desenvolva");
    expect(diagnosticar("[duracao] roteiro marca 69s (máximo 60s). Respeite.", "iniciante").problema).toBe("O vídeo passa do tempo: cerca de 69 s de fala, e o máximo é 60 s.");
  });

  it("juiz: afirmação sem base e critério do nível com a dica que já vem na mensagem", () => {
    expect(diagnosticar("[juiz] afirmação sem suporte nos fatos (remova ou reescreva): Bancos digitais subiram 104%.", "iniciante").problema)
      .toBe("O juiz não achou base no documento para: “Bancos digitais subiram 104%.”");
    const c = diagnosticar("[juiz] critério do nível não atendido: O texto tem foco analítico. Acrescente uma frase com a implicação analítica.", "avancado");
    expect(c.problema).toBe("Faltou um critério do nível Avançado: O texto tem foco analítico.");
    expect(c.sugestao).toBe("Acrescente uma frase com a implicação analítica.");
  });

  it("falhas de gráfico viram problema e sugestão próprios", () => {
    expect(diagnosticar("[formato] slide 3 com gráfico tem 140 caracteres de texto (máximo 120). Respeite.", "iniciante"))
      .toEqual({ problema: "O slide 3 tem gráfico e 140 caracteres de texto; com gráfico, o máximo é 120.",
        sugestao: "Deixe no texto só o comentário do gráfico: os números já aparecem nele." });
    expect(diagnosticar("[formato] gráfico no slide 1: o gancho e a conclusão não levam gráfico. X", "iniciante").sugestao)
      .toBe("Mova o gráfico para um dos slides do meio.");
    expect(diagnosticar("[numeros] gráfico traz o número '6,1', que não existe na âncora. Remova.", "iniciante").problema)
      .toBe("O número 6,1 não está no documento (aparece no gráfico).");
  });

  it("falha do serviço não é culpa do texto", () => {
    const d = diagnosticar("[juiz] não foi possível avaliar (HTTP 429: {\"error\":{}})", "iniciante");
    expect(d.tecnico).toBe(true);
    expect(d.sugestao).toContain("Não é um problema do texto");
    expect(diagnosticar("[formato] a resposta não obedeceu ao formato pedido (ReadTimeout: x). Responda no schema.", "avancado").tecnico).toBe(true);
  });

  it("mensagem desconhecida separa o problema da instrução", () => {
    expect(diagnosticar("[nova] algo deu errado. Faça outra coisa.", "iniciante")).toEqual({ problema: "algo deu errado.", sugestao: "Faça outra coisa." });
  });
});

describe("diagnosticos", () => {
  it("põe os bloqueios primeiro e não repete o mesmo problema", () => {
    const t = { falhas: [
      "[legibilidade] Flesch 50.0 fora da faixa 60 a 100.",
      "[numeros] número '7' não existe na âncora.",
      "[numeros] número '7' não existe na âncora.",
    ], metricas: { nota: { bloqueios: ["numeros"] } } } as unknown as Tentativa;
    const d = diagnosticos(t, "iniciante");
    expect(d.map((x) => x.problema)).toEqual(["O número 7 não está no documento.", "Texto difícil demais para o nível Iniciante: índice de leitura 50,0, esperado de 60 a 100."]);
  });
});
