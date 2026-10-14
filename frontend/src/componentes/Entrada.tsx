import { useState } from "react";
import type { Opcoes } from "../api";
import { FORMATOS, NIVEIS, ROTULO_FORMATO, ROTULO_NIVEL, type Formato, type Nivel } from "../tipos";

const SUGESTOES = ["Copom", "Inflação", "Estabilidade financeira", "Fundos de investimento"];
type Modo = "termo" | "link" | "pdf";
export type Pedido = { tipo: "termo" | "link"; valor: string } | { tipo: "pdf"; arquivo: File };

interface Props { ocupado: boolean; erro: string | null; aviso?: string | null; onGerar: (p: Pedido, o: Opcoes) => void }

export default function Entrada({ ocupado, erro, aviso, onGerar }: Props) {
  const [modo, setModo] = useState<Modo>("termo");
  const [termo, setTermo] = useState("");
  const [link, setLink] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [prioritario, setPrioritario] = useState<Nivel | "">("");
  const [tentativas, setTentativas] = useState(3);
  const [forcar, setForcar] = useState(false);
  const [niveis, setNiveis] = useState<Nivel[]>([...NIVEIS]);
  const [formatos, setFormatos] = useState<Formato[]>([...FORMATOS]);

  const escolha = niveis.length > 0 && formatos.length > 0;
  const linkValido = /^https:\/\/\S+$/i.test(link.trim());
  const pronto = escolha && (modo === "termo" ? termo.trim().length > 1 : modo === "link" ? linkValido : arquivo !== null);
  const alternar = <T,>(lista: T[], item: T, ordem: readonly T[]) =>
    ordem.filter((x) => (x === item ? !lista.includes(x) : lista.includes(x)));

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    const o: Opcoes = { niveis, formatos, prioritario: prioritario && niveis.includes(prioritario) ? prioritario : null, tentativas, forcar };
    if (modo === "pdf" && arquivo) onGerar({ tipo: "pdf", arquivo }, o);
    else if (modo === "link") onGerar({ tipo: "link", valor: link.trim() }, o);
    else if (modo === "termo") onGerar({ tipo: "termo", valor: termo.trim() }, o);
  }

  return (
    <form className="cartao" onSubmit={enviar}>
      <h1 className="grande">Transforme um documento financeiro em conteúdo para o seu público</h1>
      <p className="apoio" style={{ marginTop: 12 }}>
        Escolha o documento. O sistema escreve 3 níveis (iniciante, intermediário e avançado) em 3 formatos e confere cada um.
      </p>

      <div className="abas" role="tablist" aria-label="Como informar o documento">
        {([["termo", "Um assunto"], ["link", "Um link"], ["pdf", "Um PDF"]] as [Modo, string][]).map(([id, nome]) => (
          <button key={id} type="button" role="tab" className="aba" aria-selected={modo === id} onClick={() => setModo(id)}>{nome}</button>
        ))}
      </div>

      {modo === "termo" && (
        <div className="campo">
          <label htmlFor="termo">Assunto: buscamos o documento oficial mais recente</label>
          <input id="termo" type="text" value={termo} onChange={(e) => setTermo(e.target.value)} placeholder="Ex.: Copom" autoComplete="off" />
          <div className="sugestoes">
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
        <div className="escolha-linha">
          <span className="legenda">Níveis</span>
          <div className="seletor" role="group" aria-label="Níveis">
            {NIVEIS.map((n) => (
              <label key={n} className="opcao">
                <input type="checkbox" checked={niveis.includes(n)} onChange={() => setNiveis(alternar(niveis, n, NIVEIS))} />
                <span>{ROTULO_NIVEL[n]}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="escolha-linha">
          <span className="legenda">Formatos</span>
          <div className="seletor" role="group" aria-label="Formatos">
            {FORMATOS.map((f) => (
              <label key={f} className="opcao">
                <input type="checkbox" checked={formatos.includes(f)} onChange={() => setFormatos(alternar(formatos, f, FORMATOS))} />
                <span>{ROTULO_FORMATO[f]}</span>
              </label>
            ))}
          </div>
        </div>
        <p className={escolha ? "legenda" : "legenda erro"}>
          {escolha ? `${niveis.length * formatos.length} ${niveis.length * formatos.length === 1 ? "conteúdo" : "conteúdos"}. Menos conteúdos, geração mais rápida.`
            : "Marque pelo menos um nível e um formato."}
        </p>
      </fieldset>

      <details className="opcoes">
        <summary>Opções</summary>
        <div className="opcoes-corpo">
          <div className="campo">
            <label htmlFor="prio">Gerar primeiro o nível</label>
            <select id="prio" value={prioritario} onChange={(e) => setPrioritario(e.target.value as Nivel | "")}>
              <option value="">Nenhum</option>
              {NIVEIS.filter((n) => niveis.includes(n)).map((n) => <option key={n} value={n}>{ROTULO_NIVEL[n]}</option>)}
            </select>
          </div>
          <div className="campo">
            <label htmlFor="tent">Tentativas por conteúdo</label>
            <select id="tent" value={tentativas} onChange={(e) => setTentativas(Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <label className="interruptor" style={{ gridColumn: "1 / -1" }}>
            <input type="checkbox" checked={forcar} onChange={(e) => setForcar(e.target.checked)} />
            Gerar uma nova versão, mesmo que já exista uma igual guardada
          </label>
        </div>
      </details>

      <div className="acoes">
        <button className="botao" disabled={!pronto || ocupado}>{ocupado ? "Gerando…" : "Gerar conteúdos"}</button>
      </div>
      {erro && <div className="alerta" role="alert">{erro}</div>}
      {aviso && !erro && <div className="alerta-suave" role="status" style={{ marginTop: 16 }}>{aviso}</div>}
    </form>
  );
}
