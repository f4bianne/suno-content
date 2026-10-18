import type { Cena, Conteudo, Grafico, TermoGlossario } from "../tipos";
import { segmentar } from "../util/destaque";
import { graficoDoSlide } from "../util/exportacao";
import { desenharGrafico } from "../util/grafico";
import { faixaDeTempo } from "../util/roteiro";

/** Texto com os termos técnicos marcados. Passe `termos = null` para mostrar o texto limpo. */
export function TextoComTermos({ texto, termos }: { texto: string; termos: TermoGlossario[] | null }) {
  if (!termos || termos.length === 0) return <>{texto}</>;
  return (
    <>
      {segmentar(texto, termos).map((t, i) =>
        t.termo ? (
          <mark key={i} className={`termo n${t.termo.nivel}`} style={{ color: "inherit" }}
            title={`${t.termo.termo} (nível ${t.termo.nivel}): ${t.termo.explicacao}`}>{t.texto}</mark>
        ) : (
          <span key={i}>{t.texto}</span>
        ))}
    </>
  );
}

interface Props { conteudo: Conteudo | null; termos: TermoGlossario[] | null }

export default function ConteudoView({ conteudo, termos }: Props) {
  const T = (texto: string) => <TextoComTermos texto={texto} termos={termos} />;   // função, não componente: não recria os elementos
  if (!conteudo) return <p className="apoio">Esta tentativa não gerou texto: a resposta do modelo não seguiu o formato pedido.</p>;

  if ("corpo" in conteudo) {
    return (
      <article className="leitura">
        <h3>{T(conteudo.titulo)}</h3>
        {conteudo.corpo.split(/\n+/).map((p, i) => <p key={i}>{T(p)}</p>)}
        <p><strong>{T(conteudo.conclusao)}</strong></p>
      </article>
    );
  }
  if ("slides" in conteudo) {
    const n = conteudo.slides.length;
    return (
      <div className="slides">
        {conteudo.slides.map((s, i) => (
          <div key={i} className={`slide${i === 0 || i === n - 1 ? " destaque" : ""}`}>
            <span className="legenda">{i === 0 ? "Gancho" : i === n - 1 ? "Conclusão" : `Slide ${i + 1}`}</span>
            <span>{T(s)}</span>
            {graficoDoSlide(conteudo.graficos, i) && <MiniGrafico g={graficoDoSlide(conteudo.graficos, i)!} />}
            <span className="legenda">{s.length} caracteres</span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <ol className="roteiro" aria-label="Cenas do roteiro">
      {conteudo.cenas.map((c: Cena, i: number) => (
        <li key={i} className="cena-roteiro">
          <div className="cena-topo">
            <span className="cena-numero">Cena {i + 1}</span>
            <span className="cena-tempo">{faixaDeTempo(c)}</span>
          </div>
          <dl className="cena-campos">
            <div><dt>Narração</dt><dd className="narracao">{T(c.fala)}</dd></div>
            <div><dt>{i === 0 ? "Ação · gancho visual" : "Ação e imagens"}</dt><dd>{c.visual}</dd></div>
          </dl>
        </li>
      ))}
    </ol>
  );
}

/** O mesmo desenho da exportação, com as cores do tema da tela (variáveis CSS, que funcionam no claro e no escuro). */
function MiniGrafico({ g }: { g: Grafico }) {
  const { svg } = desenharGrafico(g, { x: 0, y: 0, largura: 360, altura: 280 },
    { tinta: "var(--ink)", apoio: "var(--muted)", grade: "var(--rule)", destaque: "var(--suno-red)" });
  return <svg className="mini-grafico" viewBox="0 0 360 280" role="img" aria-label={`Gráfico: ${g.titulo}`}
    dangerouslySetInnerHTML={{ __html: svg }} />;
}
