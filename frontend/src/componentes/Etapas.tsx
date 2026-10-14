import { useEffect, useState } from "react";
import type { Evento } from "../tipos";
import { duracao, etapasDosEventos, formatarSegundos } from "../util/etapas";

interface Props { eventos: Evento[]; total: number }

/** Linha do tempo do processamento: o que já foi feito, o que está andando agora e quanto cada etapa levou. */
export default function Etapas({ eventos, total }: Props) {
  const [decorrido, setDecorrido] = useState(0);
  useEffect(() => {
    const t0 = Date.now();
    const id = setInterval(() => setDecorrido((Date.now() - t0) / 1000), 500);
    return () => clearInterval(id);
  }, []);
  const etapas = etapasDosEventos(eventos, total);
  // O relógio local alimenta só a etapa que está andando; as concluídas usam o tempo medido pelo servidor.
  const ultimoT = eventos.length ? eventos[eventos.length - 1].t : 0;
  const agora = Math.max(decorrido, ultimoT);

  return (
    <div className="etapas">
      <p className="legenda">Tempo decorrido: <b>{formatarSegundos(agora)}</b></p>
      <ol aria-label="Etapas do processamento">
        {etapas.map((e) => {
          const d = duracao(e, agora);
          return (
            <li key={e.id} className={`etapa ${e.estado}`} aria-current={e.estado === "andando" ? "step" : undefined}>
              <span className="marca" aria-hidden="true">{e.estado === "feita" ? "✓" : e.estado === "andando" ? "●" : "○"}</span>
              <span className="nome">{e.nome}{e.id === "escrever" && e.estado !== "pendente" && e.detalhe ? ` · ${e.detalhe}` : ""}</span>
              <span className="tempo">{e.estado === "pendente" || d === null ? "aguardando" : formatarSegundos(d)}</span>
            </li>
          );
        })}
      </ol>
      {eventos.length > 0 && agora - ultimoT > 30 && (
        <p className="legenda">
          Sem novidades há {formatarSegundos(agora - ultimoT)}. Os provedores de IA limitam o uso por minuto, então às vezes o sistema espera antes de continuar.
        </p>
      )}
    </div>
  );
}
