import { useEffect, useState } from "react";
import { verRelacionados } from "../api";
import type { Relacionado } from "../tipos";
import { dataBr } from "../util/conteudo";

interface Props { execucaoId: string | null; onAbrir: (id: string) => void }

/** Outros documentos que falam das mesmas coisas, pelas entidades dos fatos (por exemplo, Selic e IPCA). */
export default function VejaTambem({ execucaoId, onAbrir }: Props) {
  const [itens, setItens] = useState<Relacionado[] | null>(null);

  useEffect(() => {
    setItens(null);
    if (!execucaoId) { setItens([]); return; }
    let ativo = true;
    verRelacionados(execucaoId).then((r) => ativo && setItens(r)).catch(() => ativo && setItens([]));
    return () => { ativo = false; };
  }, [execucaoId]);

  if (itens === null) return <p className="apoio">Procurando documentos relacionados…</p>;
  if (itens.length === 0) return <p className="apoio">Nenhum outro documento gerado fala das mesmas coisas. Quando houver, ele aparece aqui.</p>;
  return (
    <ul className="lista">
      {itens.map((r) => (
        <li key={r.id}>
          <button type="button" onClick={() => onAbrir(r.id)}>
            <span>
              <span className="titulo">{r.origem}</span>
              <span className="legenda" style={{ display: "block" }}>
                Também fala de {r.entidades_comuns.join(", ")} · {dataBr(r.criado_em)}
              </span>
            </span>
            <span className="apoio" style={{ whiteSpace: "nowrap" }}>{r.aprovados} de {r.ramos} aprovados</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
