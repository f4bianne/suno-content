# Níveis de sofisticação

Roadmap, Fase 0, item 1. Cada nível é definido pelo case e traduzido em regras que o avaliador consegue verificar. Valores numéricos são **hipóteses** até a calibração (item 7).

## Definições do case

| Nível | Definição |
|---|---|
| Iniciante | Zero jargão financeiro desacompanhado de analogia cotidiana; foco no impacto prático no bolso |
| Intermediário | Vocabulário de mercado padrão (CDI, Selic, IPCA, dividendos); foco em alocação e tendências |
| Avançado / Institucional | Jargão pleno preservado (curva de juros, forward guidance, hiato do produto, EBITDA ajustado, covenants); foco analítico e metodológico |

## Regras mensuráveis

| | Iniciante | Intermediário | Avançado |
|---|---|---|---|
| Termo do glossário nível 3 | Proibido | Só com explicação | Livre |
| Termo do glossário nível 2 | Só com analogia ou explicação | Livre | Livre |
| Termo do glossário nível 1 | Livre | Livre | Livre |
| Legibilidade (Flesch PT-BR) | 60 a 100 | 40 a 60 | 0 a 40 |
| Cobertura dos fatos da âncora | Mínimo 80% | Mínimo 80% | Mínimo 90% |
| Números | Todos devem existir na âncora | Idem | Idem |
| Linguagem de recomendação | Zero | Zero | Zero |

Os critérios qualitativos (analogia cotidiana, foco no bolso, alocação e tendências, nuance e metodologia) ficam com o Juiz LLM.

## O glossário e o nível de cada termo

O glossário (`dados/glossario.yaml`) dá a cada termo um **nível mínimo**: o menor nível em que ele aparece sem explicação. A regra foi calibrada nas âncoras do case:

| Nível | Critério | Exemplos |
|---|---|---|
| 1 | Vocabulário do dia a dia | juros, inflação, poupança, dívida, salário, Pix |
| 2 | Vocabulário de mercado padrão: tem verbete em glossário aberto para leigos (Banco Central, B3, CVM), ou é sinônimo direto | Selic, IPCA, CDI, dividendos, taxa de câmbio, dívida pública |
| 3 | Jargão institucional: aparece em atas, relatórios e releases e **não tem verbete** nos glossários leigos | curva de juros, forward guidance, hiato do produto, balanço de riscos, EBITDA ajustado, covenants |

**Verificação:** as quatro âncoras do intermediário (Selic, IPCA, CDI, dividendos) têm verbete no glossário do Banco Central, e as cinco do avançado não aparecem em nenhum glossário aberto consultado. A frequência nos documentos **não** separa os níveis: "hiato do produto" aparece em 65 dos 155 documentos do corpus, e "Selic" em 142, mas o primeiro é nível 3. Por isso a regra é a presença em glossário leigo, e a frequência (`docs_corpus`) serve só para conferir se o termo é de fato usado nos documentos.

Um teste (`tests/test_glossario.py`) garante que as âncoras do case estejam sempre nos níveis certos.

Um termo conta como **explicado** quando, na mesma frase ou na anterior, aparece um marcador de explicação ("ou seja", "isto é", "que é", "como se fosse", travessão ou parênteses seguidos de definição). Casos ambíguos vão para o Juiz.

## Métricas

- **Legibilidade:** Flesch Reading Ease adaptado ao português (Martins et al., 1996): `248,835 − 1,015 × (palavras / sentenças) − 84,6 × (sílabas / palavras)`, com sílabas contadas por Pyphen (`pt_BR`). Em carrossel, cada slide é uma sentença; no roteiro, só a fala.
- **Densidade de termos:** proporção de termos de cada nível do glossário no texto, e quais deles vêm com explicação.
- **Cobertura da âncora:** fração dos fatos centrais do documento que continuam no texto. Impede que o loop passe na legibilidade apenas encurtando.
- **Números:** todo valor citado precisa existir na âncora.
- **Linguagem de recomendação:** lista de padrões proibidos ("compre", "venda", "vale a pena aplicar" etc.).

## Pontos para decidir na calibração (item 7)

- [ ] Faixa de legibilidade por nível **e** formato, ou só por nível?
- [ ] Os limiares de cobertura (80% e 90%) são realistas? Dependem de quantos fatos o Extrator produz.
- [ ] O que conta como "explicação": só marcadores textuais, ou o Juiz decide sempre?
- [ ] Densidade mínima de termos de nível 2 e 3 no avançado, para o texto não "descer de nível" por simplificação.
- [ ] Nível dos termos de balanço (EBITDA, covenants, payout): o corpus quase não tem releases de empresas, então esses níveis são provisórios.
