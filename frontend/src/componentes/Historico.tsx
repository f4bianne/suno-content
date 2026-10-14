import type { ResumoExecucao } from "../tipos";
import { dataBr } from "../util/conteudo";

interface Props { itens: ResumoExecucao[]; onAbrir: (id: string) => void }

export default function Historico({ itens, onAbrir }: Props) {
  return (
    <section className="cartao" aria-labelledby="t-hist">
      <h2 className="rotulo-secao" id="t-hist">Gerados antes</h2>
      {itens.length === 0 ? (
        <p className="apoio">Nada gerado ainda. O primeiro resultado aparece aqui.</p>
      ) : (
        <ul className="lista">
          {itens.map((x) => (
            <li key={x.id}>
              <button type="button" onClick={() => onAbrir(x.id)}>
                <span>
                  <span className="titulo">{x.origem}</span>
                  <span className="legenda" style={{ display: "block" }}>{dataBr(x.criado_em)}{x.escopo === "sessao" ? " · só você vê" : ""}</span>
                </span>
                <span className="apoio" style={{ whiteSpace: "nowrap" }}>{x.aprovados} de {x.ramos} aprovados</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
