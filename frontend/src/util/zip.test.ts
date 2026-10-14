import { describe, expect, it } from "vitest";
import { crc32, criarZip } from "./zip";

describe("zip", () => {
  it("calcula o CRC-32 conhecido de 'abc'", () => {
    expect(crc32(new TextEncoder().encode("abc"))).toBe(0x352441c2);
  });

  it("monta cabeçalhos, nomes e conteúdo na ordem esperada", () => {
    const z = criarZip([{ nome: "a.txt", dados: new TextEncoder().encode("oi") }, { nome: "slide-02.png", dados: new Uint8Array([1, 2, 3]) }]);
    const v = new DataView(z.buffer);
    expect(v.getUint32(0, true)).toBe(0x04034b50);                       // 1º arquivo
    expect(new TextDecoder().decode(z.slice(30, 35))).toBe("a.txt");
    expect(new TextDecoder().decode(z.slice(35, 37))).toBe("oi");
    const fim = z.length - 22;
    expect(v.getUint32(fim, true)).toBe(0x06054b50);                     // fim do diretório central
    expect(v.getUint16(fim + 10, true)).toBe(2);                         // dois arquivos
    const inicioCentral = v.getUint32(fim + 16, true);
    expect(v.getUint32(inicioCentral, true)).toBe(0x02014b50);
    expect(v.getUint32(inicioCentral + 16, true)).toBe(crc32(new TextEncoder().encode("oi")));
  });
});
