import { useState } from "react";
import type { Processamento, Ramo } from "../tipos";
import { AVISO_IMAGEM, baixar, folhaSvg, nomeDoArquivo, promptImagem, slideSvgCompleto } from "../util/exportacao";

interface Props { resultado: Processamento; ramo: Ramo }

/** Leva o conteúdo aprovado para quem faz a arte: slides em SVG (o Figma importa) e prompt para IA de imagem. */
export default function ExportarDesign({ resultado, ramo }: Props) {
  const [copiado, setCopiado] = useState(false);
  const slides = ramo.conteudo && "slides" in ramo.conteudo ? ramo.conteudo.slides : null;
  const prompt = promptImagem(resultado, ramo);

  async function copiar() {
    try { await navigator.clipboard.writeText(prompt); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }
    catch { setCopiado(false); }   // sem permissão de área de transferência: o texto continua visível para copiar à mão
  }

  return (
    <div>
      {slides ? (
        <>
          <p className="apoio">
            O carrossel sai em SVG, com a identidade da Suno. No Figma, arraste o arquivo para a tela: cada slide chega como um grupo
            com nome (slide-1-gancho, slide-2-corpo...), e quem faz a arte continua no controle do acabamento.
          </p>
          <div className="acoes">
            <button type="button" className="botao-contorno" onClick={() => baixar(nomeDoArquivo(resultado, ramo, "svg"), folhaSvg(slides), "image/svg+xml")}>
              Baixar os slides (SVG)
            </button>
          </div>
          <details style={{ marginTop: 12 }}>
            <summary className="apoio" style={{ cursor: "pointer" }}>Baixar um slide de cada vez</summary>
            <div className="acoes">
              {slides.map((s, i) => (
                <button key={i} type="button" className="botao-contorno"
                  onClick={() => baixar(nomeDoArquivo(resultado, ramo, `slide${i + 1}.svg`), slideSvgCompleto(s, i, slides.length), "image/svg+xml")}>
                  Slide {i + 1}
                </button>
              ))}
            </div>
          </details>
        </>
      ) : (
        <p className="apoio">A exportação em slides vale para o carrossel. Escolha o formato Carrossel para baixar. O prompt de imagem abaixo existe para todos os formatos.</p>
      )}

      <h4 className="titulo" style={{ margin: "20px 0 8px" }}>Prompt para IA de imagem</h4>
      <p className="alerta-suave">{AVISO_IMAGEM}</p>
      <label className="legenda" htmlFor="prompt-imagem" style={{ display: "block", margin: "12px 0 4px" }}>Prompt (você pode editar antes de copiar)</label>
      <textarea id="prompt-imagem" className="area-texto" defaultValue={prompt} key={prompt} rows={8} />
      <div className="acoes">
        <button type="button" className="botao-contorno" onClick={copiar}>{copiado ? "Copiado" : "Copiar prompt"}</button>
        <button type="button" className="botao-contorno" onClick={() => baixar(nomeDoArquivo(resultado, ramo, "prompt.txt"), prompt, "text/plain")}>Baixar (.txt)</button>
      </div>
    </div>
  );
}
