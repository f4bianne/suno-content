"""Preenche o histórico com entradas de exemplo de link e PDF, copiando gerações reais do banco.

O conteúdo é sempre de uma geração real: cada link aponta para o endereço oficial do documento que foi gerado, e cada
PDF é um documento que foi gerado de verdade (experimentos, envios ou o PDF oficial baixado). No banco, tudo fica
marcado (`entrada.exemplo` e `sha256_bruto = "exemplo"`), fora do cache e removível de uma vez.

Uso:
  python scripts/exemplos.py             cria os exemplos (não duplica se já existirem)
  python scripts/exemplos.py --remover   apaga tudo o que este script criou
"""
import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

BANCO = Path(__file__).resolve().parent.parent / "dados" / "suno.db"
MARCA = "exemplo"


def execucoes_reais(c: sqlite3.Connection, documento_id: int, limite: int):
    return c.execute("select * from execucoes where documento_id = ? and config_hash != ? order by criado_em desc limit ?",
                     (documento_id, MARCA, limite)).fetchall()


def documento_publico(c: sqlite3.Connection, d: sqlite3.Row, nome: str) -> int:
    cur = c.execute("insert into documentos (chave, escopo, sessao, tipo, origem, url, sha256_bruto, paginas, palavras, coletado_em, texto)"
                    " values (?, 'publico', '', 'pdf', ?, null, ?, ?, ?, ?, ?)",
                    (f"{d['chave'][:52]}-{uuid.uuid4().hex[:8]}", nome, MARCA, d["paginas"], d["palavras"], d["coletado_em"], d["texto"]))
    return cur.lastrowid


def copiar_execucao(c: sqlite3.Connection, e: sqlite3.Row, documento_id: int, entrada: dict) -> str:
    novo = uuid.uuid4().hex[:12]
    config = json.loads(e["config"])
    config["entrada"] = {**entrada, MARCA: True}
    criado = datetime.fromisoformat(e["criado_em"]) + timedelta(minutes=3)
    c.execute("insert into execucoes (id, documento_id, criado_em, config_hash, config, niveis, formatos, ancora, descartados, segundos)"
              " values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (novo, documento_id, criado.isoformat(sep=" "), MARCA, json.dumps(config, ensure_ascii=False), e["niveis"],
               e["formatos"], e["ancora"], e["descartados"], e["segundos"]))
    for r in c.execute("select * from ramos where execucao_id = ?", (e["id"],)).fetchall():
        cur = c.execute("insert into ramos (execucao_id, nivel, formato, status, conteudo) values (?, ?, ?, ?, ?)",
                        (novo, r["nivel"], r["formato"], r["status"], r["conteudo"]))
        for t in c.execute("select * from tentativas where ramo_id = ?", (r["id"],)).fetchall():
            c.execute("insert into tentativas (ramo_id, n, aprovado, falhas, metricas, veredito, conteudo, segundos_geracao,"
                      " segundos_avaliacao, chamadas_llm) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (cur.lastrowid, t["n"], t["aprovado"], t["falhas"], t["metricas"], t["veredito"], t["conteudo"],
                       t["segundos_geracao"], t["segundos_avaliacao"], t["chamadas_llm"]))
    return novo


def criar(c: sqlite3.Connection) -> None:
    if c.execute("select count(*) from execucoes where config_hash = ?", (MARCA,)).fetchone()[0]:
        print("Os exemplos já existem. Para refazer: --remover e depois rode de novo.")
        return
    reais = "sha256_bruto != 'exemplo'"
    # Links: até 3 gerações reais por endereço oficial de documento público.
    por_url: dict[str, int] = {}
    for d in c.execute(f"select * from documentos where escopo = 'publico' and url is not null and {reais} order by id desc").fetchall():
        for e in execucoes_reais(c, d["id"], 3 - por_url.get(d["url"], 0)):
            nome = (json.loads(e["config"]).get("entrada") or {}).get("documento") or d["origem"]
            copiar_execucao(c, e, d["id"], {"tipo": "link", "valor": d["url"], "documento": nome})
            por_url[d["url"]] = por_url.get(d["url"], 0) + 1
            print(f"link: {d['url']}")
    # PDFs: gerações reais feitas a partir de PDF (experimentos e envios) e os documentos oficiais como o PDF baixado.
    arquivos = set()
    for d in c.execute(f"select * from documentos where tipo = 'pdf' and escopo = 'sessao' and {reais}").fetchall():
        arquivos.add(d["origem"])
        for e in execucoes_reais(c, d["id"], 2):
            copiar_execucao(c, e, documento_publico(c, d, d["origem"]), {"tipo": "pdf", "valor": d["origem"], "documento": None})
            print(f"pdf: {d['origem']}")
    for d in c.execute(f"select * from documentos where escopo = 'publico' and url is not null and {reais} order by id desc").fetchall():
        arquivo = d["url"].rsplit("/", 1)[-1]
        if arquivo in arquivos or not (e := execucoes_reais(c, d["id"], 1)):
            continue
        arquivos.add(arquivo)
        copiar_execucao(c, e[0], documento_publico(c, d, arquivo), {"tipo": "pdf", "valor": arquivo, "documento": None})
        print(f"pdf: {arquivo}")


def remover(c: sqlite3.Connection) -> None:
    ids = [r[0] for r in c.execute("select id from execucoes where config_hash = ?", (MARCA,))]
    for i in ids:
        c.execute("delete from tentativas where ramo_id in (select id from ramos where execucao_id = ?)", (i,))
        c.execute("delete from ramos where execucao_id = ?", (i,))
        c.execute("delete from acessos where execucao_id = ?", (i,))
        c.execute("delete from execucoes where id = ?", (i,))
    docs = c.execute("delete from documentos where sha256_bruto = ?", (MARCA,)).rowcount
    print(f"Removidos {len(ids)} exemplos e {docs} documentos de exemplo.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    a = argparse.ArgumentParser()
    a.add_argument("--remover", action="store_true")
    args = a.parse_args()
    c = sqlite3.connect(BANCO)
    c.row_factory = sqlite3.Row
    with c:
        remover(c) if args.remover else criar(c)


if __name__ == "__main__":
    main()
