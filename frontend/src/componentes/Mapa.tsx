import { FORMATOS, NIVEIS, ROTULO_FORMATO, ROTULO_NIVEL, type EstadoCelula, type Formato, type Nivel, type Processamento } from "../tipos";

export const chaveCelula = (n: Nivel, f: Formato) => `${n}|${f}`;

interface Props {
  resultado: Processamento | null;
  ao_vivo: Record<string, EstadoCelula>;
  pedidos?: string[];   // células pedidas (chaveCelula); sem isso, vale que todas foram pedidas
  selecao?: { nivel: Nivel; formato: Formato };
  onSelecionar?: (nivel: Nivel, formato: Formato) => void;
  ocupado?: boolean;
}

/** Os 9 conteúdos de uma vez. Verde mais forte = aprovou com menos tentativas. */
export default function Mapa({ resultado, ao_vivo, selecao, onSelecionar, ocupado, pedidos }: Props) {
  return (
    <div>
      <div className="mapa" role="group" aria-label="Os 9 conteúdos: níveis por formatos">
        <div />
        {FORMATOS.map((f) => <div key={f} className="cab">{ROTULO_FORMATO[f]}</div>)}
        {NIVEIS.map((n) => (
          <Linha key={n} nivel={n} resultado={resultado} ao_vivo={ao_vivo} selecao={selecao} onSelecionar={onSelecionar} ocupado={ocupado} pedidos={pedidos} />
        ))}
      </div>
      <p className="legenda" style={{ marginTop: 12 }}>
        ▲ aprovado (verde mais forte = menos tentativas) · ▼ bloqueado depois de todas as tentativas
      </p>
    </div>
  );
}

function Linha({ nivel, resultado, ao_vivo, selecao, onSelecionar, ocupado, pedidos }: Props & { nivel: Nivel }) {
  return (
    <>
      <div className="linha">{ROTULO_NIVEL[nivel]}</div>
      {FORMATOS.map((f) => {
        const ramo = resultado?.ramos.find((r) => r.nivel === nivel && r.formato === f);
        const vivo = ao_vivo[chaveCelula(nivel, f)];
        let classe = "", estado = "—", miudo = "";
        if (ramo) {
          const n = ramo.tentativas.length;
          estado = ramo.status === "aprovado" ? "▲ Aprovado" : "▼ Bloqueado";
          classe = ramo.status === "aprovado" ? `bom-${Math.min(n, 3)}` : "ruim";
          miudo = n === 1 ? "de primeira" : `${n} tentativas`;
        } else if (vivo) {
          classe = "viva";
          estado = vivo.fase === "gerando" ? "Escrevendo…" : vivo.aprovado ? "Finalizando…" : "Refazendo…";
          miudo = `tentativa ${vivo.tentativa}`;
        } else if (ocupado && pedidos && !pedidos.includes(chaveCelula(nivel, f))) {
          estado = "Não pedido"; miudo = "fora desta geração";
        } else if (ocupado) {
          classe = "viva";
          estado = "Na fila";
        }
        const selecionada = selecao?.nivel === nivel && selecao.formato === f;
        return (
          <button key={f} type="button" className={`celula ${classe}`} disabled={!ramo || !onSelecionar} aria-pressed={selecionada}
            aria-label={`${ROTULO_NIVEL[nivel]}, ${ROTULO_FORMATO[f]}: ${estado}`} onClick={() => onSelecionar?.(nivel, f)}>
            <span className="estado">{estado}</span>
            {miudo && <span className="miudo">{miudo}</span>}
          </button>
        );
      })}
    </>
  );
}
