import { useState } from "react";
import { type Config, type Formato, type Nivel, type Processamento, type ResumoExecucao, type TermoGlossario } from "../tipos";
import ExportarDesign from "./ExportarDesign";
import OutrasVersoes from "./OutrasVersoes";
import VejaTambem from "./VejaTambem";

interface Props {
  resultado: Processamento;
  config: Config | null;
  historico: ResumoExecucao[];
  termos: TermoGlossario[] | null;
  nivel: Nivel;
  formato: Formato;
  onAbrir: (id: string) => void;
}

/** Recursos de apoio, todos recolhidos: quem só quer ler o conteúdo nem precisa vê-los. */
export default function Extras({ resultado, config, historico, termos, nivel, formato, onAbrir }: Props) {
  const ramo = resultado.ramos.find((r) => r.nivel === nivel && r.formato === formato);
  const [aberto, setAberto] = useState(false);   // o conteúdo só é montado depois de aberto: nada pesado na tela inicial
  return (
    <details className="secao-recolhida" onToggle={(e) => setAberto((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>Mais recursos</summary>
      {aberto && <div className="extras">
        <section aria-labelledby="x-design">
          <h3 className="titulo" id="x-design">Levar para o design</h3>
          {ramo ? <ExportarDesign resultado={resultado} ramo={ramo} /> : <p className="apoio">Escolha um conteúdo gerado.</p>}
        </section>
        <section aria-labelledby="x-versoes">
          <h3 className="titulo" id="x-versoes">Comparar com outra versão</h3>
          <OutrasVersoes atual={resultado} historico={historico} nivel={nivel} formato={formato} termos={termos} config={config} />
        </section>
        <section aria-labelledby="x-tambem">
          <h3 className="titulo" id="x-tambem">Veja também</h3>
          <VejaTambem execucaoId={resultado.execucao_id} onAbrir={onAbrir} />
        </section>
      </div>}
    </details>
  );
}
