import type { ResumoExecucao, TipoEntrada } from "../tipos";
import { dataBr } from "../util/conteudo";

interface Props { itens: ResumoExecucao[]; onAbrir: (id: string) => void }

/** Cada geração aparece pelo que a pessoa usou: o termo pesquisado, o link ou o nome do PDF. */
const GRUPOS: { tipo: TipoEntrada; titulo: string }[] = [
  { tipo: "termo", titulo: "Termos pesquisados" },
  { tipo: "link", titulo: "Links" },
  { tipo: "pdf", titulo: "PDFs enviados" },
];

export default function Historico({ itens, onAbrir }: Props) {
  const grupos = GRUPOS.map((g) => ({ ...g, itens: itens.filter((x) => x.tipo === g.tipo) })).filter((g) => g.itens.length > 0);
  return (
    <section className="cartao" aria-labelledby="t-hist">
      <h2 className="rotulo-secao" id="t-hist">Gerados antes</h2>
      {itens.length === 0 ? (
        <p className="apoio">Nada gerado ainda. O primeiro resultado aparece aqui.</p>
      ) : (
        grupos.map((g) => (
          <div key={g.tipo} className="grupo-historico">
            <h3 className="legenda">{g.titulo}</h3>
            <ul className="lista">
              {g.itens.map((x) => (
                <li key={x.id}>
                  <button type="button" onClick={() => onAbrir(x.id)}>
                    <span style={{ minWidth: 0 }}>
                      <span className="titulo" style={g.tipo === "link" ? { overflowWrap: "anywhere" } : undefined}>{x.origem}</span>
                      <span className="legenda" style={{ display: "block" }}>
                        {x.documento_nome ? `${x.documento_nome} · ` : ""}{dataBr(x.criado_em)}{x.escopo === "sessao" ? " · só você vê" : ""}
                      </span>
                    </span>
                    <span className="apoio" style={{ whiteSpace: "nowrap" }}>{x.aprovados} de {x.ramos} aprovados</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
