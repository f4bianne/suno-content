import { useEffect, useState } from "react";
import { verExecucao } from "../api";
import { ROTULO_FORMATO, ROTULO_NIVEL, type Config, type Formato, type Nivel, type Processamento, type ResumoExecucao, type TermoGlossario } from "../tipos";
import { checagens, faixaFlesch } from "../util/avaliacao";
import { dataBr, textoDe } from "../util/conteudo";
import { diferenca, proporcaoAlterada } from "../util/diff";
import ConteudoView from "./ConteudoView";

interface Props {
  atual: Processamento;
  historico: ResumoExecucao[];
  nivel: Nivel;
  formato: Formato;
  termos: TermoGlossario[] | null;
  config: Config | null;
}

/** Quando o mesmo documento foi gerado mais de uma vez, mostra duas versões lado a lado. */
export default function OutrasVersoes({ atual, historico, nivel, formato, termos, config }: Props) {
  const outras = historico.filter((h) => h.documento === atual.documento_chave && h.id !== atual.execucao_id);
  const [escolhida, setEscolhida] = useState<string>("");
  const [outra, setOutra] = useState<Processamento | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [verDiff, setVerDiff] = useState(false);

  useEffect(() => {
    setOutra(null); setErro(null); setVerDiff(false);
    if (!escolhida) return;
    let ativo = true;
    verExecucao(escolhida).then((p) => ativo && setOutra(p)).catch((e) => ativo && setErro(e instanceof Error ? e.message : String(e)));
    return () => { ativo = false; };
  }, [escolhida]);

  if (outras.length === 0) {
    return <p className="apoio">Este documento foi gerado uma vez só. Para ter uma segunda versão e comparar, gere de novo marcando "Gerar uma nova versão" nas opções.</p>;
  }

  const minha = atual.ramos.find((r) => r.nivel === nivel && r.formato === formato);
  const dela = outra?.ramos.find((r) => r.nivel === nivel && r.formato === formato);
  const partes = minha?.conteudo && dela?.conteudo ? diferenca(textoDe(dela.conteudo), textoDe(minha.conteudo)) : [];

  const coluna = (titulo: string, p: Processamento, r: typeof minha) => {
    if (!r) return <div className="coluna"><span className="titulo">{titulo}</span><p className="apoio">Esse conteúdo não existe nesta versão.</p></div>;
    const ult = r.tentativas[r.tentativas.length - 1];
    const falhou = checagens(ult, r, config).filter((c) => c.estado === "falhou").length;
    const faixa = faixaFlesch(config, r);
    return (
      <div className="coluna">
        <div>
          <span className="titulo">{titulo}</span>{" "}
          <span className={`selo ${r.status === "aprovado" ? "ok" : "ruim"}`}>{r.status === "aprovado" ? "▲ aprovado" : "▼ bloqueado"}</span>
        </div>
        <p className="legenda">
          {dataBr(p.gerado_em)} · {r.tentativas.length} {r.tentativas.length === 1 ? "tentativa" : "tentativas"}
          {ult.metricas.flesch !== undefined && ` · leitura ${ult.metricas.flesch}${faixa ? ` (esperado ${faixa[0]} a ${faixa[1]})` : ""}`}
          {falhou > 0 && ` · ${falhou} ${falhou === 1 ? "conferência falhou" : "conferências falharam"}`}
        </p>
        {p.config.modelos && <p className="legenda">Escrito por {p.config.modelos.gerador}</p>}
        <ConteudoView conteudo={r.conteudo} termos={termos} />
      </div>
    );
  };

  return (
    <div>
      <p className="apoio">Compare a versão que você está vendo com outra geração do mesmo documento, no mesmo nível e formato ({ROTULO_NIVEL[nivel]}, {ROTULO_FORMATO[formato]}).</p>
      <div className="campo" style={{ margin: "12px 0", maxWidth: 420 }}>
        <label htmlFor="outra-versao">Comparar com</label>
        <select id="outra-versao" value={escolhida} onChange={(e) => setEscolhida(e.target.value)}>
          <option value="">Escolha uma versão</option>
          {outras.map((o) => <option key={o.id} value={o.id}>{dataBr(o.criado_em)}: {o.aprovados} de {o.ramos} aprovados</option>)}
        </select>
      </div>
      {erro && <div className="alerta" role="alert">{erro}</div>}
      {outra && (
        <>
          <div className="duas-colunas">
            {coluna("Esta versão", atual, minha)}
            {coluna("Outra versão", outra, dela)}
          </div>
          {partes.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <button type="button" className="botao-contorno" onClick={() => setVerDiff(!verDiff)} aria-pressed={verDiff}>
                {verDiff ? "Esconder a diferença" : "Ver a diferença entre as duas"}
              </button>
              {verDiff && (
                <>
                  <p className="legenda" style={{ margin: "12px 0 8px" }}>
                    {Math.round(proporcaoAlterada(partes) * 100)}% do texto é diferente. <del>Riscado</del> só existe na outra versão, <ins>sublinhado</ins> só existe nesta.
                  </p>
                  <div className="diff">
                    {partes.map((p, i) => p.tipo === "igual" ? <span key={i}>{p.texto} </span>
                      : p.tipo === "removido" ? <del key={i}>{p.texto} </del> : <ins key={i}>{p.texto} </ins>)}
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
