import { useState } from "react";
import type { ResumoExecucao, TipoEntrada } from "../tipos";
import { dataBr } from "../util/conteudo";

interface Props { itens: ResumoExecucao[]; onAbrir: (id: string) => void }

/** Cada geração aparece pelo que a pessoa usou: o termo pesquisado, o link ou o nome do PDF, numa aba por tipo. */
const ABAS: { tipo: TipoEntrada; titulo: string; vazio: string }[] = [
  { tipo: "termo", titulo: "Termos", vazio: "Nenhum termo pesquisado ainda." },
  { tipo: "link", titulo: "Links", vazio: "Nenhum link gerado ainda." },
  { tipo: "pdf", titulo: "PDFs", vazio: "Nenhum PDF enviado nesta sessão. PDFs ficam visíveis só para quem enviou." },
];

export default function Historico({ itens, onAbrir }: Props) {
  const porTipo = (t: TipoEntrada) => itens.filter((x) => x.tipo === t);
  const [escolhida, setEscolhida] = useState<TipoEntrada | null>(null);
  // Enquanto a pessoa não escolhe, abre na primeira aba que tem alguma coisa.
  const aba = escolhida ?? ABAS.find((a) => porTipo(a.tipo).length > 0)?.tipo ?? "termo";
  const atual = ABAS.find((a) => a.tipo === aba)!;
  const lista = porTipo(aba);
  return (
    <section className="cartao" aria-labelledby="t-hist">
      <h2 className="rotulo-secao" id="t-hist">Gerados antes</h2>
      {itens.length === 0 ? (
        <p className="apoio">Nada gerado ainda. O primeiro resultado aparece aqui.</p>
      ) : (
        <>
          <div className="abas" role="tablist" aria-label="Tipo de entrada">
            {ABAS.map((a) => (
              <button key={a.tipo} type="button" role="tab" className="aba" id={`hist-${a.tipo}`} aria-controls="hist-painel"
                aria-selected={aba === a.tipo} onClick={() => setEscolhida(a.tipo)}>
                {a.titulo} ({porTipo(a.tipo).length})
              </button>
            ))}
          </div>
          <div role="tabpanel" id="hist-painel" aria-labelledby={`hist-${aba}`}>
            {lista.length === 0 ? (
              <p className="apoio">{atual.vazio}</p>
            ) : (
              <ul className="lista">
                {lista.map((x) => (
                  <li key={x.id}>
                    <button type="button" onClick={() => onAbrir(x.id)}>
                      <span style={{ minWidth: 0 }}>
                        <span className="titulo" style={aba === "link" ? { overflowWrap: "anywhere" } : undefined}>{x.origem}</span>
                        <span className="legenda" style={{ display: "block" }}>
                          {x.documento_nome ? `${x.documento_nome} · ` : ""}{dataBr(x.criado_em)}{x.escopo === "sessao" ? " · só você vê" : ""}
                        </span>
                      </span>
                      <span className="apoio" style={{ whiteSpace: "nowrap" }}>{x.aprovados} de {x.ramos} aprovados</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  );
}
