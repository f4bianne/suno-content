"""API: recebe termo, link ou PDF, roda o pipeline em segundo plano e expõe progresso, resultado e histórico.

Execução: python -m uvicorn api.main:app --reload
"""
import asyncio
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from avaliador import avaliar as av
from avaliador import glossario
from avaliador.juiz import ClienteGroq
from geracao import grafo
from geracao.schemas import FORMATOS
from ingestao import entrada
from ingestao.clientes import ClienteGemini
from ingestao.documento import Documento, ErroIngestao

RAIZ = Path(__file__).resolve().parent.parent
SAIDAS = RAIZ / "dados" / "saidas"
LIMITE_PDF = 26 * 1024 * 1024


def clientes_padrao() -> grafo.Clientes:
    """Extrator e juiz na Groq (gpt-oss-120b) e gerador no Gemini, como na seção 8 do roadmap."""
    groq = ClienteGroq()
    return grafo.Clientes(extrator=groq, gerador=ClienteGemini(), juiz=groq)


class PedidoJob(BaseModel):
    tipo: Literal["termo", "link"]
    valor: str
    niveis: list[str] = list(av.NIVEIS)
    formatos: list[str] = list(FORMATOS)
    prioritario: str | None = None
    tentativas: int = 3
    concorrencia: int = 2


@dataclass
class Job:
    id: str
    entrada: dict
    status: str = "ingerindo"            # ingerindo | processando | concluido | erro
    eventos: list[dict] = field(default_factory=list)
    resultado: dict | None = None
    erro: str | None = None
    criado_em: float = field(default_factory=time.time)

    def publicar(self, evento: dict) -> None:
        self.eventos.append({**evento, "t": round(time.time() - self.criado_em, 1)})


def criar_app(fabrica_clientes: Callable[[], grafo.Clientes] = clientes_padrao,
              ingestor: Callable[..., Documento] | None = None, pasta_saidas: Path = SAIDAS,
              cfg: dict | None = None) -> FastAPI:
    app = FastAPI(title="Suno Content")
    indice = glossario.Indice(glossario.carregar())
    jobs: dict[str, Job] = {}
    pool = ThreadPoolExecutor(max_workers=2)
    trava = threading.Lock()

    def ingerir(job: Job, tipo: str, valor: Any, nome: str | None) -> Documento:
        if ingestor is not None:
            return ingestor(tipo, valor, nome, indice)
        if tipo == "termo":
            return entrada.ingerir_termo(valor, indice)
        if tipo == "link":
            return entrada.ingerir_link(valor, indice)
        return entrada.ingerir_pdf(valor, nome or "documento.pdf", indice)

    def executar(job: Job, pedido: PedidoJob, tipo: str, valor: Any, nome: str | None) -> None:
        try:
            job.publicar({"tipo": "ingerindo"})
            doc = ingerir(job, tipo, valor, nome)
            p = doc.proveniencia
            job.publicar({"tipo": "documento", "origem": p.origem, "url": p.url, "palavras": len(doc.texto.split()),
                          "paginas": doc.paginas})
            job.status = "processando"
            proc = grafo.processar(
                doc, fabrica_clientes(), indice, cfg, niveis=tuple(pedido.niveis), formatos=tuple(pedido.formatos),
                nivel_prioritario=pedido.prioritario, max_tentativas=pedido.tentativas, concorrencia=pedido.concorrencia,
                observador=lambda ev: job.publicar(ev),
            )
            pasta_saidas.mkdir(parents=True, exist_ok=True)
            # Nada é substituído: cada geração vira uma execução própria (hash do documento + data e hora).
            nome_arquivo = f"{proc.documento_chave[:12]}-{proc.gerado_em:%Y%m%d%H%M%S}"
            (pasta_saidas / f"{nome_arquivo}.json").write_text(proc.model_dump_json(indent=2), encoding="utf-8")
            job.resultado = json.loads(proc.model_dump_json())
            job.status = "concluido"
            job.publicar({"tipo": "fim", "chave": nome_arquivo})
        except ErroIngestao as e:
            job.erro, job.status = str(e), "erro"
            job.publicar({"tipo": "erro", "mensagem": job.erro})
        except Exception as e:   # chave ausente, API fora do ar etc.
            job.erro, job.status = f"{type(e).__name__}: {str(e)[:300]}", "erro"
            job.publicar({"tipo": "erro", "mensagem": job.erro})

    def abrir(pedido: PedidoJob, tipo: str, valor: Any, nome: str | None, info: dict) -> dict:
        for n in pedido.niveis:
            if n not in av.NIVEIS:
                raise HTTPException(422, f"nível desconhecido: {n}")
        for f in pedido.formatos:
            if f not in FORMATOS:
                raise HTTPException(422, f"formato desconhecido: {f}")
        job = Job(id=uuid.uuid4().hex[:10], entrada=info)
        with trava:
            jobs[job.id] = job
        pool.submit(executar, job, pedido, tipo, valor, nome)
        return {"id": job.id}

    @app.post("/api/jobs")
    def criar_job(pedido: PedidoJob):
        if not pedido.valor.strip():
            raise HTTPException(422, "informe um termo ou um link")
        return abrir(pedido, pedido.tipo, pedido.valor, None, {"tipo": pedido.tipo, "valor": pedido.valor})

    @app.post("/api/jobs/pdf")
    async def criar_job_pdf(request: Request, nome: str = "documento.pdf", niveis: str = ",".join(av.NIVEIS),
                            formatos: str = ",".join(FORMATOS), prioritario: str | None = None):
        dados = await request.body()
        if len(dados) > LIMITE_PDF:
            raise HTTPException(413, "PDF grande demais")
        pedido = PedidoJob(tipo="termo", valor="-", niveis=niveis.split(","), formatos=formatos.split(","), prioritario=prioritario)
        return abrir(pedido, "pdf", dados, nome, {"tipo": "pdf", "valor": nome})

    def pegar(job_id: str) -> Job:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job não encontrado")
        return job

    @app.get("/api/jobs/{job_id}")
    def ver_job(job_id: str):
        j = pegar(job_id)
        return {"id": j.id, "status": j.status, "entrada": j.entrada, "erro": j.erro, "eventos": j.eventos, "resultado": j.resultado}

    @app.get("/api/jobs/{job_id}/eventos")
    async def eventos(job_id: str):
        j = pegar(job_id)

        async def fluxo():
            enviados = 0
            while True:
                while enviados < len(j.eventos):
                    yield f"data: {json.dumps(j.eventos[enviados], ensure_ascii=False)}\n\n"
                    enviados += 1
                if j.status in ("concluido", "erro") and enviados >= len(j.eventos):
                    return
                await asyncio.sleep(0.4)

        return StreamingResponse(fluxo(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/api/execucoes")
    def listar_execucoes():
        itens = []
        for arq in sorted(pasta_saidas.glob("*.json"), key=lambda a: a.stat().st_mtime, reverse=True):
            try:
                d = json.loads(arq.read_text(encoding="utf-8"))
                status = [r["status"] for r in d["ramos"]]
                itens.append({"chave": arq.stem, "origem": d["origem"], "url": d.get("url"), "gerado_em": d.get("gerado_em"),
                              "ramos": len(status), "aprovados": status.count("aprovado")})
            except (ValueError, KeyError):
                continue
        return itens

    @app.get("/api/execucoes/{chave}")
    def ver_execucao(chave: str):
        arq = pasta_saidas / f"{Path(chave).name}.json"   # Path(...).name impede sair da pasta
        if not arq.exists():
            raise HTTPException(404, "execução não encontrada")
        return json.loads(arq.read_text(encoding="utf-8"))

    @app.get("/api/config")
    def configuracao():
        c = cfg or av.carregar_config()
        return {"niveis": list(av.NIVEIS), "formatos": list(FORMATOS), "limiares": c["niveis"], "formato_limites": c["formatos"]}

    return app


app = criar_app()
