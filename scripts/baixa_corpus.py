"""Baixa o corpus listado em dados/corpus.yaml para dados/corpus/ (fora do git).

Arquivos que já existem são mantidos. Endereços inexistentes (404) são ignorados.
Uso: python scripts/baixa_corpus.py
"""
import concurrent.futures as cf
import json
import os
import sys
import urllib.error
import urllib.request

import yaml

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = "dados/corpus"
CABECALHO = {"User-Agent": "Mozilla/5.0"}


def baixar(destino, url, so_pdf):
    if os.path.exists(destino):
        return "ja existia"
    try:
        req = urllib.request.Request(url, headers=CABECALHO)
        dados = urllib.request.urlopen(req, timeout=90).read()
    except urllib.error.HTTPError as e:
        return "inexistente" if e.code == 404 else f"erro {e.code}"
    except Exception as e:  # rede, tempo esgotado
        return f"erro {type(e).__name__}"
    if so_pdf and dados[:4] != b"%PDF":
        return "nao e PDF"
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(dados)
    return "baixado"


def tarefas(cfg):
    atas = cfg["atas_copom"]
    req = urllib.request.Request(atas["api"], headers=CABECALHO)
    for r in json.load(urllib.request.urlopen(req, timeout=60))["conteudo"]:
        if r["nroReuniao"] < atas["reuniao_minima"]:
            continue
        data = r["dataReferencia"]
        url = atas["url"].format(nro=r["nroReuniao"], data=data.replace("-", ""))
        yield f"{RAIZ}/{atas['pasta']}/ata_{r['nroReuniao']:03d}_{data}.pdf", url, True
    for p in cfg["padroes"]:
        for ano in range(p["anos"][0], p["anos"][1] + 1):
            for mes in p["meses"]:
                if "desde_2025" in p["urls"]:
                    chave = "desde_2025" if ano >= 2025 else "ate_2024"
                else:
                    chave = "todos"
                url = p["urls"][chave].format(ano=ano, mes=mes)
                yield f"{RAIZ}/{p['pasta']}/{p['arquivo'].format(ano=ano, mes=mes)}", url, True
    for a in cfg["arquivos"]:
        yield f"{RAIZ}/{a['pasta']}/{a['arquivo']}", a["url"], a["arquivo"].endswith(".pdf")


def main():
    with open("dados/corpus.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    lista = list(tarefas(cfg))
    with cf.ThreadPoolExecutor(5) as ex:
        resultados = list(ex.map(lambda t: baixar(*t), lista))
    contagem = {}
    for r in resultados:
        contagem[r] = contagem.get(r, 0) + 1
    print(len(lista), "endereços:", contagem)
    for m in cfg["manuais"]:
        destino = f"{RAIZ}/{m['pasta']}/{m['arquivo']}"
        if not os.path.exists(destino):
            print(f"Baixar à mão: {destino} ({m['url']}) - {m['nota']}")


if __name__ == "__main__":
    main()
