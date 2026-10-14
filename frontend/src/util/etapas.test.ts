import { describe, expect, it } from "vitest";
import type { Evento } from "../tipos";
import { duracao, etapasDosEventos, formatarSegundos } from "./etapas";

const ev = (tipo: string, t: number, extra: Partial<Evento> = {}): Evento => ({ tipo, t, ...extra });

describe("etapas do processamento", () => {
  it("começa com a primeira etapa andando e as outras aguardando", () => {
    const e = etapasDosEventos([ev("ingerindo", 0)], 9);
    expect(e.map((x) => x.estado)).toEqual(["andando", "pendente", "pendente", "pendente"]);
    expect(duracao(e[0], 4)).toBe(4);
    expect(duracao(e[1], 4)).toBeNull();
  });

  it("mede cada etapa pelos tempos do servidor", () => {
    const e = etapasDosEventos([ev("ingerindo", 0), ev("documento", 3.2), ev("extraindo", 3.2), ev("ancora", 20.7), ev("gerando", 21)], 9);
    expect(e.map((x) => x.estado)).toEqual(["feita", "feita", "andando", "pendente"]);
    expect(duracao(e[0], 99)).toBeCloseTo(3.2);
    expect(duracao(e[1], 99)).toBeCloseTo(17.5);
    expect(duracao(e[2], 30)).toBeCloseTo(9.3);
    expect(e[2].detalhe).toBe("0 de 9 prontos");
  });

  it("conta os conteúdos prontos e fecha as etapas ao terminar", () => {
    const base = [ev("ingerindo", 0), ev("documento", 2), ev("extraindo", 2), ev("ancora", 10)];
    const parcial = etapasDosEventos([...base, ev("ramo_fim", 40), ev("ramo_fim", 55)], 9);
    expect(parcial[2].detalhe).toBe("2 de 9 prontos");
    expect(parcial[2].estado).toBe("andando");
    const fim = etapasDosEventos([...base, ev("ramo_fim", 50), ev("ramo_fim", 60), ev("fim", 62)], 2);
    expect(fim.map((x) => x.estado)).toEqual(["feita", "feita", "feita", "feita"]);
    expect(duracao(fim[3], 99)).toBeCloseTo(2);
  });

  it("resultado do cache tem uma etapa só", () => {
    const e = etapasDosEventos([ev("ingerindo", 0), ev("documento", 1.5), ev("cache", 1.6), ev("fim", 1.7)], 9);
    expect(e).toHaveLength(1);
    expect(e[0].nome).toBe("Buscar o resultado guardado");
    expect(e[0].estado).toBe("feita");
  });

  it("formata o tempo em segundos e minutos", () => {
    expect(formatarSegundos(3.24)).toBe("3,2 s");
    expect(formatarSegundos(42.4)).toBe("42 s");
    expect(formatarSegundos(125)).toBe("2 min 05 s");
  });
});
