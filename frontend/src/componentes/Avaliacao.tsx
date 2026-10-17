import { useState } from "react";
import type { Config, Ramo, Tentativa } from "../tipos";
import { checagens, nota, resumir, type Estado } from "../util/avaliacao";
import { textoDe } from "../util/conteudo";
import { diferenca, proporcaoAlterada } from "../util/diff";
import { diagnosticos } from "../util/melhoria";

const SIMBOLO: Record<Estado, string> = { ok: "✓", aviso: "!", falhou: "✕", nao_rodou: "–" };
const ROTULO: Record<Estado, string> = { ok: "passou", aviso: "passou com ressalva", falhou: "não passou", nao_rodou: "não chegou a rodar" };

/** "Nota 0,91 (mínimo 0,85)", com o motivo quando a nota sozinha não explica a reprovação. */
function linhaDaNota(n: NonNullable<Tentativa["metricas"]["nota"]>): string {
  const base = `Nota ${nota(n.total)} (mínimo ${nota(n.limiar)})`;
  if (n.bloqueios.length) return `${base}, mas bloqueada por: ${n.bloqueios.join(", ")}`;
  if (n.abaixo_do_piso.length) return `${base}, mas abaixo do mínimo em: ${n.abaixo_do_piso.join(", ")}`;
  return base;
}

function manchete(ramo: Ramo, final: Tentativa, aprovadas: number, total: number): string {
  const n = final.metricas.nota;
  if (ramo.status === "aprovado") {
    if (!n) return "Passou em todas as conferências";      // versões antigas, de antes da nota
    return aprovadas === total ? `Passou em todas as conferências · nota ${nota(n.total)}` : `Aprovado com nota ${nota(n.total)} (mínimo ${nota(n.limiar)}), com ressalvas`;
  }
  return n ? `${linhaDaNota(n)} · passou em ${aprovadas} de ${total} conferências` : `Passou em ${aprovadas} de ${total} conferências`;
}

const MAX_PROBLEMAS = 5;

/** Conteúdo bloqueado: cada problema da versão final, em linguagem simples, com o que mudar no texto. */
function PorQue({ ramo, final }: { ramo: Ramo; final: Tentativa }) {
  const [todos, setTodos] = useState(false);
  const lista = diagnosticos(final, ramo.nivel);
  if (lista.length === 0) return null;
  const visiveis = todos ? lista : lista.slice(0, MAX_PROBLEMAS);
  return (
    <div className="por-que" role="region" aria-label="Por que não foi publicado">
      <p className="titulo">Por que não foi publicado</p>
      <p className="apoio">
        {ramo.tentativas.length > 1 ? `Depois de ${ramo.tentativas.length} tentativas, ` : ""}a última versão ainda tinha {lista.length === 1 ? "este problema" : `estes ${lista.length} problemas`}
        {lista.length > 1 ? ", do mais grave para o mais leve" : ""}:
      </p>
      <ol>
        {visiveis.map((d, i) => (
          <li key={i} className={d.tecnico ? "tecnico" : undefined}>
            <span style={{ display: "block" }}>{d.problema}</span>
            <span className="sugestao-melhoria"><strong>Como melhorar:</strong> {d.sugestao}</span>
          </li>
        ))}
      </ol>
      {lista.length > MAX_PROBLEMAS && (
        <button type="button" className="botao-contorno" onClick={() => setTodos(!todos)}>
          {todos ? "Mostrar só os principais" : `Ver mais ${lista.length - MAX_PROBLEMAS}`}
        </button>
      )}
    </div>
  );
}

interface Props { ramo: Ramo; config: Config | null }

/** Responde, em linguagem simples, "esse conteúdo está bom?" e, se foi reescrito, "o que mudou?". */
export default function Avaliacao({ ramo, config }: Props) {
  const [verDiff, setVerDiff] = useState(false);
  const final = ramo.tentativas[ramo.tentativas.length - 1];
  const lista = checagens(final, ramo, config);
  const aprovadas = lista.filter((c) => c.estado === "ok").length;
  const reescrito = ramo.tentativas.length > 1;
  const primeiro = ramo.tentativas.find((t) => t.conteudo)?.conteudo ?? null;
  const partes = reescrito && primeiro && final.conteudo ? diferenca(textoDe(primeiro), textoDe(final.conteudo)) : [];

  return (
    <section className="cartao" aria-labelledby="t-aval">
      <h2 className="rotulo-secao" id="t-aval">Como foi avaliado</h2>
      <p className="manchete">{manchete(ramo, final, aprovadas, lista.length)}</p>
      {ramo.status !== "aprovado" && <PorQue ramo={ramo} final={final} />}
      <ul className="checagens">
        {lista.map((c) => (
          <li key={c.id}>
            <span className={`marca ${c.estado}`} aria-label={ROTULO[c.estado]}>{SIMBOLO[c.estado]}</span>
            <span>
              <span className="titulo">{c.titulo}</span>
              <span className="apoio" style={{ display: "block" }}>{c.detalhe}</span>
              {c.motivo && <span className="motivo" style={{ display: "block" }}>{c.motivo}</span>}
            </span>
          </li>
        ))}
      </ul>

      <details className="tentativas">
        <summary>{reescrito ? `O texto foi escrito ${ramo.tentativas.length} vezes. Ver o caminho` : "Escrito de primeira"}</summary>
        {ramo.tentativas.map((t, i) => {
          const motivo = t.falhas[0] ? resumir(t.falhas[0].replace(/^\[[^\]]+\]\s*/, ""), 120) : null;
          return (
            <div className="passo" key={i}>
              <span className="titulo">
                Tentativa {i + 1}: <span className={t.aprovado ? "selo ok" : "selo ruim"}>{t.aprovado ? "▲ aprovada" : "▼ reprovada"}</span>
              </span>
              {t.metricas.nota && <span className="apoio">{linhaDaNota(t.metricas.nota)}.</span>}
              {motivo && <span className="apoio">{t.falhas.length > 1 ? `${t.falhas.length} ${t.aprovado ? "ressalvas" : "problemas"}. Primeiro: ` : t.aprovado ? "Ressalva: " : "Problema: "}{motivo}</span>}
              {t.metricas.explicacoes_inseridas && t.metricas.explicacoes_inseridas.length > 0 && (
                <span className="legenda">O sistema acrescentou a definição do glossário em: {t.metricas.explicacoes_inseridas.join(", ")}.</span>
              )}
              {!t.aprovado && i < ramo.tentativas.length - 1 && (
                t.metricas.plano_revisao ? (
                  <details className="plano-revisor">
                    <summary className="legenda">O revisor leu as falhas e montou um plano para a reescrita</summary>
                    <p className="apoio">{t.metricas.plano_revisao.diagnostico}</p>
                    <ol>{t.metricas.plano_revisao.acoes.map((a, k) => <li key={k}>{a}</li>)}</ol>
                    {t.metricas.plano_revisao.manter.length > 0 && (
                      <p className="legenda">Manter: {t.metricas.plano_revisao.manter.join(" · ")}</p>
                    )}
                  </details>
                ) : <span className="legenda">O relatório de falhas foi entregue ao gerador, que reescreveu.</span>
              )}
            </div>
          );
        })}
        {partes.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <button type="button" className="botao-contorno" onClick={() => setVerDiff(!verDiff)} aria-pressed={verDiff}>
              {verDiff ? "Esconder o que mudou" : "Ver o que mudou"}
            </button>
            {verDiff && (
              <>
                <p className="legenda" style={{ margin: "12px 0 8px" }}>
                  Da primeira versão para a final: {Math.round(proporcaoAlterada(partes) * 100)}% do texto mudou. <del>Riscado</del> saiu, <ins>sublinhado</ins> entrou.
                </p>
                <div className="diff">
                  {partes.map((p, i) => p.tipo === "igual" ? <span key={i}>{p.texto} </span>
                    : p.tipo === "removido" ? <del key={i}>{p.texto} </del> : <ins key={i}>{p.texto} </ins>)}
                </div>
              </>
            )}
          </div>
        )}
      </details>
    </section>
  );
}
