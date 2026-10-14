import type { Processamento } from "../tipos";
import { dataBr } from "../util/conteudo";

/** A fonte de tudo o que foi escrito: cada fato com o trecho literal do documento. */
export default function Fatos({ resultado }: { resultado: Processamento }) {
  const modelos = resultado.config.modelos;
  return (
    <div>
      <p>
        <strong>Documento: </strong>
        {resultado.url ? <a href={resultado.url} target="_blank" rel="noreferrer noopener">{resultado.url}</a> : resultado.origem}
      </p>
      <p className="apoio" style={{ marginTop: 4 }}>
        Gerado em {dataBr(resultado.gerado_em)}
        {modelos ? ` · escrito por ${modelos.gerador}, revisado por ${modelos.juiz}` : ""}
      </p>
      <h3 className="titulo" style={{ margin: "20px 0 8px" }}>Fatos em que os textos se apoiam</h3>
      <p className="apoio" style={{ marginBottom: 12 }}>
        Cada fato só entrou porque o trecho abaixo existe, palavra por palavra, no documento.
        {resultado.fatos_descartados.length > 0 && ` O modelo propôs outros ${resultado.fatos_descartados.length}, descartados por não baterem com o documento.`}
      </p>
      <table>
        <thead><tr><th>Fato</th><th>Trecho do documento</th></tr></thead>
        <tbody>
          {resultado.ancora.fatos.map((f) => (
            <tr key={f.id}>
              <td>
                {f.texto}
                {f.numeros.length > 0 && <span className="legenda" style={{ display: "block" }}>Números: {f.numeros.join(", ")}</span>}
              </td>
              <td><blockquote style={{ margin: 0 }}>{f.trecho_origem}</blockquote></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
