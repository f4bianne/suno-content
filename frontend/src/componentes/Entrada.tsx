import { useState } from "react";
import type { Opcoes } from "../api";
import { FORMATOS, NIVEIS, ROTULO_FORMATO, ROTULO_NIVEL, type Formato, type Nivel } from "../tipos";

// Cada sugestão é uma chave de dados/ingestao.yaml: sempre acha um documento oficial.
const SUGESTOES = ["Copom", "Selic", "Juros", "Inflação", "IPCA", "Câmbio", "Crédito", "Inadimplência",
  "Estabilidade financeira", "Fundos de investimento", "FII", "Política monetária", "Expectativas de inflação", "Taxa de juros",
  "Sistema financeiro", "Fiagro"];
type Modo = "termo" | "link" | "pdf";
export type Pedido = { tipo: "termo" | "link"; valor: string } | { tipo: "pdf"; arquivo: File };

interface Props { ocupado: boolean; erro: string | null; aviso?: string | null; onGerar: (p: Pedido, o: Opcoes) => void }

export default function Entrada({ ocupado, erro, aviso, onGerar }: Props) {
  const [modo, setModo] = useState<Modo>("termo");
  const [termo, setTermo] = useState("");
  const [link, setLink] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [niveis, setNiveis] = useState<Nivel[]>([...NIVEIS]);
  const [formatos, setFormatos] = useState<Formato[]>([...FORMATOS]);

  const escolha = niveis.length > 0 && formatos.length > 0;
  const linkValido = /^https:\/\/\S+$/i.test(link.trim());
  const pronto = escolha && (modo === "termo" ? termo.trim().length > 1 : modo === "link" ? linkValido : arquivo !== null);
  const alternar = <T,>(lista: T[], item: T, ordem: readonly T[]) =>
    ordem.filter((x) => (x === item ? !lista.includes(x) : lista.includes(x)));

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    const o: Opcoes = { niveis, formatos, prioritario: null, tentativas: 2, forcar: false };
    if (modo === "pdf" && arquivo) onGerar({ tipo: "pdf", arquivo }, o);
    else if (modo === "link") onGerar({ tipo: "link", valor: link.trim() }, o);
    else if (modo === "termo") onGerar({ tipo: "termo", valor: termo.trim() }, o);
  }

  return (
    <form className="cartao" onSubmit={enviar}>
      <h1 className="grande">Um documento oficial, três leitores, nove conteúdos.</h1>

      <div className="abas" role="tablist" aria-label="Como informar o documento">
        {([["termo", "Um assunto"], ["link", "Um link"], ["pdf", "Um PDF"]] as [Modo, string][]).map(([id, nome]) => (
          <button key={id} type="button" role="tab" className="aba" aria-selected={modo === id} onClick={() => setModo(id)}>{nome}</button>
        ))}
      </div>

      {modo === "termo" && (
        <div className="campo">
          <label htmlFor="termo">Assunto: buscamos o documento oficial mais recente</label>
          <input id="termo" type="text" value={termo} onChange={(e) => setTermo(e.target.value)} placeholder="Ex.: Copom" autoComplete="off" />
          <div className="sugestoes" role="group" aria-label="Sugestões de assunto">
            <span className="legenda">Sugestões:</span>
            {SUGESTOES.map((s) => <button key={s} type="button" className="sugestao" onClick={() => setTermo(s)}>{s}</button>)}
          </div>
        </div>
      )}
      {modo === "link" && (
        <div className="campo">
          <label htmlFor="link">Link do documento (https, de uma fonte oficial como BCB, CVM, Tesouro ou B3)</label>
          <input id="link" type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://www.bcb.gov.br/..." autoComplete="off" />
        </div>
      )}
      {modo === "pdf" && (
        <div className="campo">
          <label htmlFor="pdf">Arquivo PDF (até 25 MB). Fica visível só para você.</label>
          <input id="pdf" type="file" accept="application/pdf" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
        </div>
      )}

      <fieldset className="escolha">
        <legend className="rotulo-secao">O que gerar</legend>
        {/* Uma barra para os níveis e outra para os formatos, lado a lado; os nomes ficam só no aria-label. */}
        <div className="escolha-barras">
          <div className="seletor" role="group" aria-label="Níveis">
            {NIVEIS.map((n) => (
              <label key={n} className="opcao">
                <input type="checkbox" checked={niveis.includes(n)} onChange={() => setNiveis(alternar(niveis, n, NIVEIS))} />
                <span>{ROTULO_NIVEL[n]}</span>
              </label>
            ))}
          </div>
          <div className="seletor" role="group" aria-label="Formatos">
            {FORMATOS.map((f) => (
              <label key={f} className="opcao">
                <input type="checkbox" checked={formatos.includes(f)} onChange={() => setFormatos(alternar(formatos, f, FORMATOS))} />
                <span>{ROTULO_FORMATO[f]}</span>
              </label>
            ))}
          </div>
        </div>
        {!escolha && <p className="legenda erro">Marque pelo menos um nível e um formato.</p>}
      </fieldset>

      <div className="acoes">
        <button className="botao" disabled={!pronto || ocupado}>{ocupado ? "Gerando…" : "Gerar conteúdos"}</button>
      </div>
      {erro && <div className="alerta" role="alert">{erro}</div>}
      {aviso && !erro && <div className="alerta-suave" role="status" style={{ marginTop: 16 }}>{aviso}</div>}
    </form>
  );
}
