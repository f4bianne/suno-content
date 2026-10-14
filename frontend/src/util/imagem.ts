/** Converte um SVG em PNG usando o próprio navegador (canvas). Só roda no navegador; os testes cobrem o SVG e o zip. */
export async function svgParaPng(svg: string, lado = 1080): Promise<Uint8Array> {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = new Image();
    img.width = lado; img.height = lado;
    await new Promise<void>((ok, erro) => { img.onload = () => ok(); img.onerror = () => erro(new Error("não foi possível desenhar o slide")); img.src = url; });
    const tela = document.createElement("canvas");
    tela.width = lado; tela.height = lado;
    const ctx = tela.getContext("2d");
    if (!ctx) throw new Error("o navegador não permite criar a imagem");
    ctx.drawImage(img, 0, 0, lado, lado);
    const blob = await new Promise<Blob | null>((ok) => tela.toBlob(ok, "image/png"));
    if (!blob) throw new Error("não foi possível gerar o PNG");
    return new Uint8Array(await blob.arrayBuffer());
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Baixa bytes ou texto como arquivo. */
export function baixarBlob(nome: string, dados: BlobPart | Uint8Array, mime: string): void {
  const url = URL.createObjectURL(new Blob([dados as BlobPart], { type: mime }));
  const a = document.createElement("a");
  a.href = url; a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
