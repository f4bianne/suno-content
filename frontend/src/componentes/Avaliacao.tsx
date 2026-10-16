import { useState } from "react";
import type { Config, Ramo } from "../tipos";
import { checagens, resumir, type Estado } from "../util/avaliacao";
import { textoDe } from "../util/conteudo";
import { diferenca, proporcaoAlterada } from "../util/diff";

const SIMBOLO: Record<Estado, string> = { ok: "✓", falhou: "✕", nao_rodou: "–" };
const ROTULO: Record<Estado, string> = { ok: "passou", falhou: "não passou", nao_rodou: "não chegou a rodar" };

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
      <p className="manchete">{ramo.status === "aprovado" ? "Passou em todas as conferências" : `Passou em ${aprovadas} de ${lista.length} conferências`}</p>
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
              {motivo && <span className="apoio">{t.falhas.length > 1 ? `${t.falhas.length} problemas. Primeiro: ` : "Problema: "}{motivo}</span>}
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
