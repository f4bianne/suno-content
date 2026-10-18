import { useState } from "react";
import type { Processamento, Ramo } from "../tipos";
import { AVISO_IMAGEM, baixar, folhaSvg, graficoDoSlide, nomeDoArquivo, promptImagem, slideSvgCompleto } from "../util/exportacao";
import { baixarBlob, svgParaPng } from "../util/imagem";
import { artigoEmHtml, artigoEmMarkdown, artigoEmTexto } from "../util/artigo";
import { roteiroEmCsv, roteiroEmMarkdown, roteiroEmTexto } from "../util/roteiro";
import { criarZip } from "../util/zip";

interface Props { resultado: Processamento; ramo: Ramo }

/** Leva o conteúdo aprovado para quem faz a arte: slides separados (PNG e SVG) e prompt para IA de imagem. */
export default function ExportarDesign({ resultado, ramo }: Props) {
  const [copiado, setCopiado] = useState(false);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const slides = ramo.conteudo && "slides" in ramo.conteudo ? ramo.conteudo.slides : null;
  const graficos = ramo.conteudo && "slides" in ramo.conteudo ? ramo.conteudo.graficos ?? [] : [];
  const completo = (i: number) => slideSvgCompleto(slides![i], i, slides!.length, graficoDoSlide(graficos, i));
  const cenas = ramo.conteudo && "cenas" in ramo.conteudo ? ramo.conteudo.cenas : null;
  const artigo = ramo.conteudo && "corpo" in ramo.conteudo ? ramo.conteudo : null;
  const [artigoCopiado, setArtigoCopiado] = useState(false);
  const prompt = promptImagem(resultado, ramo);
  const [roteiroCopiado, setRoteiroCopiado] = useState(false);
  const tituloRoteiro = `${resultado.origem} (${ramo.nivel})`;

  async function copiar() {
    try { await navigator.clipboard.writeText(prompt); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }
    catch { setCopiado(false); }   // sem permissão de área de transferência: o texto continua visível para copiar à mão
  }

  async function executar(chave: string, tarefa: () => Promise<void>) {
    setOcupado(chave); setErro(null);
    try { await tarefa(); } catch (e) { setErro(e instanceof Error ? e.message : String(e)); } finally { setOcupado(null); }
  }

  async function copiarRoteiro() {
    if (!cenas) return;
    try { await navigator.clipboard.writeText(roteiroEmTexto(tituloRoteiro, cenas)); setRoteiroCopiado(true); setTimeout(() => setRoteiroCopiado(false), 2000); }
    catch { setRoteiroCopiado(false); }
  }

  async function copiarArtigo() {
    if (!artigo) return;
    try { await navigator.clipboard.writeText(artigoEmTexto(artigo, resultado, ramo)); setArtigoCopiado(true); setTimeout(() => setArtigoCopiado(false), 2000); }
    catch { setArtigoCopiado(false); }
  }

  const png = (i: number) => svgParaPng(completo(i));
  const baixarPng = (i: number) => executar(`png${i}`, async () => baixarBlob(nomeDoArquivo(resultado, ramo, `slide-${i + 1}.png`), await png(i), "image/png"));
  const baixarZip = () => executar("zip", async () => {
    const arquivos = [];
    for (let i = 0; i < slides!.length; i++) arquivos.push({ nome: `slide-${String(i + 1).padStart(2, "0")}.png`, dados: await png(i) });
    baixarBlob(nomeDoArquivo(resultado, ramo, "slides.zip"), criarZip(arquivos), "application/zip");
  });

  return (
    <div>
      {slides ? (
        <>
          <p className="apoio">Cada slide é uma imagem quadrada (1080 por 1080) pronta para postar, com a identidade da Suno.</p>
          <div className="grade-slides">
            {slides.map((s, i) => (
              <figure key={i} className="slide-miniatura">
                <div className="slide-imagem" role="img" aria-label={`Slide ${i + 1}: ${s}`}
                  dangerouslySetInnerHTML={{ __html: completo(i) }} />
                <figcaption>
                  <span className="legenda">Slide {i + 1}</span>
                  <span className="slide-acoes">
                    <button type="button" className="botao-texto" disabled={ocupado !== null} onClick={() => baixarPng(i)}>
                      {ocupado === `png${i}` ? "Gerando…" : "PNG"}
                    </button>
                    <button type="button" className="botao-texto"
                      onClick={() => baixar(nomeDoArquivo(resultado, ramo, `slide-${i + 1}.svg`), completo(i), "image/svg+xml")}>
                      SVG
                    </button>
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
          <div className="acoes">
            <button type="button" className="botao-contorno" disabled={ocupado !== null} onClick={baixarZip}>
              {ocupado === "zip" ? "Gerando as imagens…" : "Baixar todos os slides (PNG, .zip)"}
            </button>
            <button type="button" className="botao-contorno" onClick={() => baixar(nomeDoArquivo(resultado, ramo, "carrossel.svg"), folhaSvg(slides, graficos), "image/svg+xml")}>
              Folha única para o Figma (SVG)
            </button>
          </div>
          {erro && <div className="alerta" role="alert">{erro}</div>}
          <h4 className="titulo" style={{ margin: "20px 0 8px" }}>Prompt para IA de imagem</h4>
          <p className="alerta-suave">{AVISO_IMAGEM}</p>
          <label className="legenda" htmlFor="prompt-imagem" style={{ display: "block", margin: "12px 0 4px" }}>Prompt (você pode editar antes de copiar)</label>
          <textarea id="prompt-imagem" className="area-texto" defaultValue={prompt} key={prompt} rows={8} />
          <div className="acoes">
            <button type="button" className="botao-contorno" onClick={copiar}>{copiado ? "Copiado" : "Copiar prompt"}</button>
            <button type="button" className="botao-contorno" onClick={() => baixar(nomeDoArquivo(resultado, ramo, "prompt.txt"), prompt, "text/plain")}>Baixar (.txt)</button>
          </div>
        </>
      ) : cenas ? (
        <>
          <p className="apoio">O roteiro sai pronto para a equipe de produção: tempo, narração e ação de cada cena.</p>
          <div className="acoes">
            <button type="button" className="botao-contorno" onClick={copiarRoteiro}>{roteiroCopiado ? "Roteiro copiado" : "Copiar roteiro"}</button>
            <button type="button" className="botao-contorno"
              onClick={() => baixar(nomeDoArquivo(resultado, ramo, "roteiro.csv"), roteiroEmCsv(cenas), "text/csv;charset=utf-8")}>
              Baixar planilha (.csv)
            </button>
            <button type="button" className="botao-contorno"
              onClick={() => baixar(nomeDoArquivo(resultado, ramo, "roteiro.txt"), roteiroEmTexto(tituloRoteiro, cenas), "text/plain;charset=utf-8")}>
              Baixar texto (.txt)
            </button>
            <button type="button" className="botao-contorno"
              onClick={() => baixar(nomeDoArquivo(resultado, ramo, "roteiro.md"), roteiroEmMarkdown(tituloRoteiro, cenas), "text/markdown;charset=utf-8")}>
              Baixar tabela (.md)
            </button>
          </div>
        </>
      ) : artigo ? (
        <>
          <p className="apoio">O artigo sai com título, texto e a fonte no rodapé, pronto para o site, a newsletter ou o e-mail.</p>
          <div className="acoes">
            <button type="button" className="botao-contorno" onClick={copiarArtigo}>{artigoCopiado ? "Artigo copiado" : "Copiar artigo"}</button>
            <button type="button" className="botao-contorno"
              onClick={() => baixar(nomeDoArquivo(resultado, ramo, "artigo.html"), artigoEmHtml(artigo, resultado, ramo), "text/html;charset=utf-8")}>
              Baixar página (.html)
            </button>
            <button type="button" className="botao-contorno"
              onClick={() => baixar(nomeDoArquivo(resultado, ramo, "artigo.md"), artigoEmMarkdown(artigo, resultado, ramo), "text/markdown;charset=utf-8")}>
              Baixar Markdown (.md)
            </button>
            <button type="button" className="botao-contorno"
              onClick={() => baixar(nomeDoArquivo(resultado, ramo, "artigo.txt"), artigoEmTexto(artigo, resultado, ramo), "text/plain;charset=utf-8")}>
              Baixar texto (.txt)
            </button>
          </div>
        </>
      ) : (
        <p className="apoio">Escolha um conteúdo gerado para exportar.</p>
      )}

    </div>
  );
}
