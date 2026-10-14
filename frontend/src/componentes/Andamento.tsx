import { ROTULO_FORMATO, ROTULO_NIVEL, type EstadoCelula, type Evento } from "../tipos";
import Etapas from "./Etapas";
import Mapa from "./Mapa";

function descrever(e: Evento): { texto: string; classe?: string } | null {
  const onde = e.nivel && e.formato ? `${ROTULO_NIVEL[e.nivel]} · ${ROTULO_FORMATO[e.formato]}` : "";
  switch (e.tipo) {
    case "ingerindo": return { texto: "Lendo o documento…" };
    case "documento": return { texto: `Documento lido: ${e.palavras} palavras${e.paginas ? `, ${e.paginas} páginas` : ""}` };
    case "cache": return { texto: "Esse resultado já existia: nenhum modelo foi chamado", classe: "ok" };
    case "extraindo": return { texto: "Extraindo os fatos principais…" };
    case "ancora": return { texto: `${e.fatos} fatos extraídos` };
    case "gerando": return { texto: `${onde}: escrevendo (tentativa ${e.tentativa})` };
    case "avaliado": return e.aprovado
      ? { texto: `${onde}: aprovado`, classe: "ok" }
      : { texto: `${onde}: não passou, vai ser reescrito`, classe: "ruim" };
    case "ramo_fim": return { texto: `${onde}: ${e.status === "aprovado" ? "pronto" : "bloqueado"}`, classe: e.status === "aprovado" ? "ok" : "ruim" };
    case "erro": return { texto: e.mensagem ?? "Erro", classe: "ruim" };
    default: return null;
  }
}

interface Props { eventos: Evento[]; ao_vivo: Record<string, EstadoCelula>; total?: number; pedidos?: string[]; onCancelar?: () => void }

export default function Andamento({ eventos, ao_vivo, total = 9, pedidos, onCancelar }: Props) {
  const prontos = Object.values(ao_vivo).filter((c) => c.fase === "fim").length;
  const doCache = eventos.some((e) => e.tipo === "cache");
  const extraindo = eventos.some((e) => e.tipo === "extraindo") && !eventos.some((e) => e.tipo === "ancora");
  const texto = doCache ? "Buscando o resultado guardado…" : extraindo ? "Lendo o documento e extraindo os fatos…"
    : prontos ? `${prontos} de ${total} conteúdos prontos` : "Preparando…";
  const linhas = eventos.map(descrever).filter((x): x is { texto: string; classe?: string } => x !== null);

  return (
    <section className="cartao" aria-live="polite">
      <h2 className="rotulo-secao">Gerando</h2>
      <p className="manchete">{texto}</p>
      <div className="barra" aria-hidden="true"><i style={{ width: `${doCache ? 100 : Math.round((prontos / total) * 100)}%` }} /></div>
      <Etapas eventos={eventos} total={total} />
      {onCancelar && (
        <div className="acoes" style={{ marginTop: 0, marginBottom: 24 }}>
          <button type="button" className="botao-contorno" onClick={onCancelar}>Cancelar geração</button>
        </div>
      )}
      <Mapa resultado={null} ao_vivo={ao_vivo} ocupado pedidos={pedidos} />
      <details className="detalhes-andamento">
        <summary>Ver detalhes</summary>
        <ul className="registro">{linhas.map((l, i) => <li key={i} className={l.classe}>{l.texto}</li>)}</ul>
      </details>
    </section>
  );
}
