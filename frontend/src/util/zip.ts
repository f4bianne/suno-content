/** Empacota arquivos em um .zip sem compressão (método "store"). PNG já é comprimido, então não perde nada. */

const TABELA = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

export function crc32(dados: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < dados.length; i++) c = TABELA[(c ^ dados[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export interface ArquivoZip { nome: string; dados: Uint8Array }

export function criarZip(arquivos: ArquivoZip[]): Uint8Array {
  const codificador = new TextEncoder();
  const partes: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let deslocamento = 0;
  // 1º de janeiro de 1980, 00:00: o formato exige uma data e ela não importa aqui
  const hora = 0, data = (0 << 9) | (1 << 5) | 1;

  for (const a of arquivos) {
    const nome = codificador.encode(a.nome);
    const crc = crc32(a.dados);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true);
    local.setUint16(6, 0x0800, true);          // nome em UTF-8
    local.setUint16(8, 0, true);               // sem compressão
    local.setUint16(10, hora, true);
    local.setUint16(12, data, true);
    local.setUint32(14, crc, true);
    local.setUint32(18, a.dados.length, true);
    local.setUint32(22, a.dados.length, true);
    local.setUint16(26, nome.length, true);
    local.setUint16(28, 0, true);
    partes.push(new Uint8Array(local.buffer), nome, a.dados);

    const reg = new DataView(new ArrayBuffer(46));
    reg.setUint32(0, 0x02014b50, true);
    reg.setUint16(4, 20, true);
    reg.setUint16(6, 20, true);
    reg.setUint16(8, 0x0800, true);
    reg.setUint16(10, 0, true);
    reg.setUint16(12, hora, true);
    reg.setUint16(14, data, true);
    reg.setUint32(16, crc, true);
    reg.setUint32(20, a.dados.length, true);
    reg.setUint32(24, a.dados.length, true);
    reg.setUint16(28, nome.length, true);
    reg.setUint32(42, deslocamento, true);
    central.push(new Uint8Array(reg.buffer), nome);
    deslocamento += 30 + nome.length + a.dados.length;
  }

  const tamanhoCentral = central.reduce((s, p) => s + p.length, 0);
  const fim = new DataView(new ArrayBuffer(22));
  fim.setUint32(0, 0x06054b50, true);
  fim.setUint16(8, arquivos.length, true);
  fim.setUint16(10, arquivos.length, true);
  fim.setUint32(12, tamanhoCentral, true);
  fim.setUint32(16, deslocamento, true);

  const todas = [...partes, ...central, new Uint8Array(fim.buffer)];
  const saida = new Uint8Array(todas.reduce((s, p) => s + p.length, 0));
  let pos = 0;
  for (const p of todas) { saida.set(p, pos); pos += p.length; }
  return saida;
}
