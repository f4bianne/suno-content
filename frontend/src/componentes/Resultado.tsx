import { useMemo, useState } from "react";
import { FORMATOS, NIVEIS, ROTULO_FORMATO, ROTULO_NIVEL, type Config, type Formato, type Nivel, type Processamento, type Ramo, type ResumoExecucao, type TermoGlossario } from "../tipos";
import { dataBr } from "../util/conteudo";
import { termosParaDestacar } from "../util/destaque";
import Avaliacao from "./Avaliacao";
import ConteudoView from "./ConteudoView";
import Extras from "./Extras";
import Fatos from "./Fatos";
import Mapa from "./Mapa";

interface Props {
  resultado: Processamento; config: Config | null; glossario: TermoGlossario[]; onNovo: () => void;
  historico?: ResumoExecucao[];
}

const selo = (r: Ramo | undefined) => (r ? (r.status === "aprovado" ? "ok" : "ruim") : "");

export default function Resultado({ resultado, config, glossario, onNovo, historico = [] }: Props) {
  const primeiro = resultado.ramos[0];
  const [nivel, setNivel] = useState<Nivel>(primeiro?.nivel ?? "iniciante");
  const [formato, setFormato] = useState<Formato>(primeiro?.formato ?? "artigo");
  const [comparar, setComparar] = useState(false);
  const [destacar, setDestacar] = useState(true);
  // O que o leitor faz na página (termos que abre, trocas de nível). Só vive aqui, no navegador.

  const termos = useMemo(() => (destacar ? termosParaDestacar(glossario) : null), [destacar, glossario]);
  const achar = (n: Nivel, f: Formato) => resultado.ramos.find((r) => r.nivel === n && r.formato === f);
  const ramo = achar(nivel, formato);
  const aprovados = resultado.ramos.filter((r) => r.status === "aprovado").length;
  const reescritos = resultado.ramos.filter((r) => r.tentativas.length > 1).length;

  return (
    <>
      <section className="cartao">
        <div className="barra-topo">
          <h2 className="rotulo-secao" style={{ margin: 0, border: 0, flex: 1 }}>Resultado</h2>
          <button type="button" className="botao-contorno" onClick={onNovo}>Novo documento</button>
        </div>
        <p className="manchete" style={{ marginTop: 12 }}>{resultado.origem}</p>
        <p className="apoio">
          {resultado.documento_nome && <>{resultado.documento_nome} · </>}
          {resultado.url && <><a href={resultado.url} target="_blank" rel="noreferrer noopener">ver o documento original</a> · </>}
          {dataBr(resultado.gerado_em)}{resultado.do_cache ? " · já estava guardado" : ""}
        </p>
        <div className="resumo">
          <div className="numero"><b className={aprovados === resultado.ramos.length ? "pos" : ""}>{aprovados} de {resultado.ramos.length}</b><span className="apoio">conteúdos aprovados</span></div>
          <div className="numero"><b>{reescritos}</b><span className="apoio">reescritos após a conferência</span></div>
        </div>
      </section>

      <section className="cartao controles" aria-label="Escolha o conteúdo">
        <div className="grupo">
          <span className="legenda">Para quem</span>
          <div className="segmentado" role="group" aria-label="Nível">
            {NIVEIS.map((n) => (
              <button key={n} type="button" aria-pressed={nivel === n} onClick={() => setNivel(n)} disabled={comparar}>
                <span className={`bolinha ${selo(achar(n, formato))}`} aria-hidden="true" />{ROTULO_NIVEL[n]}
              </button>
            ))}
          </div>
        </div>
        <div className="grupo">
          <span className="legenda">Em que formato</span>
          <div className="segmentado" role="group" aria-label="Formato">
            {FORMATOS.map((f) => (
              <button key={f} type="button" aria-pressed={formato === f} onClick={() => setFormato(f)}>
                <span className={`bolinha ${selo(achar(nivel, f))}`} aria-hidden="true" />{ROTULO_FORMATO[f]}
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          <label className="interruptor">
            <input type="checkbox" checked={comparar} onChange={(e) => setComparar(e.target.checked)} /> Comparar os 3 níveis lado a lado
          </label>
          <label className="interruptor">
            <input type="checkbox" checked={destacar} onChange={(e) => setDestacar(e.target.checked)} /> Marcar termos técnicos
          </label>
        </div>
      </section>

      {comparar ? (
        <section className="cartao" aria-label="Comparação dos níveis">
          <h2 className="rotulo-secao">{ROTULO_FORMATO[formato]}: os 3 níveis</h2>
          <div className="colunas">
            {NIVEIS.map((n) => {
              const r = achar(n, formato);
              return (
                <div className="coluna" key={n}>
                  <div>
                    <span className="titulo">{ROTULO_NIVEL[n]}</span>{" "}
                    {r && <span className={`selo ${selo(r)}`}>{r.status === "aprovado" ? "▲ aprovado" : "▼ bloqueado"}</span>}
                  </div>
                  {r ? <ConteudoView conteudo={r.conteudo} termos={termos} /> : <p className="apoio">Não gerado.</p>}
                </div>
              );
            })}
          </div>
          {destacar && <Legenda />}
        </section>
      ) : ramo ? (
        <>
          <section className="cartao" aria-label={`${ROTULO_NIVEL[nivel]}, ${ROTULO_FORMATO[formato]}`}>
            <div className="barra-topo" style={{ marginBottom: 16 }}>
              <h2 className="rotulo-secao" style={{ margin: 0, border: 0 }}>{ROTULO_NIVEL[nivel]} · {ROTULO_FORMATO[formato]}</h2>
              <span className={`selo ${selo(ramo)}`}>{ramo.status === "aprovado" ? "▲ Aprovado" : "▼ Bloqueado"}</span>
            </div>
            <ConteudoView conteudo={ramo.conteudo} termos={termos} />
            {destacar && <Legenda />}
          </section>
          <Avaliacao key={`${nivel}|${formato}`} ramo={ramo} config={config} />
        </>
      ) : (
        <section className="cartao"><p className="apoio">Esse conteúdo não foi gerado.</p></section>
      )}

      <details className="secao-recolhida">
        <summary>Visão geral dos 9 conteúdos</summary>
        <div>
          <Mapa resultado={resultado} ao_vivo={{}} selecao={{ nivel, formato }}
            onSelecionar={(n, f) => { setNivel(n); setFormato(f); setComparar(false); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
        </div>
      </details>
      <details className="secao-recolhida">
        <summary>Fatos e fonte do documento</summary>
        <div><Fatos resultado={resultado} /></div>
      </details>
      <Extras resultado={resultado} config={config} historico={historico} termos={termos} nivel={nivel} formato={formato} />
    </>
  );
}

function Legenda() {
  return (
    <div className="legenda-termos legenda">
      <span style={{ flexBasis: "100%" }}>Passe o mouse sobre o termo para ver o que significa:</span>
      <span><mark className="termo n2" style={{ color: "inherit" }}>termo de mercado</mark> conhecido por quem investe</span>
      <span><mark className="termo n3" style={{ color: "inherit" }}>jargão institucional</mark> de especialistas</span>
    </div>
  );
}
