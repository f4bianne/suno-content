"""API: recebe termo, link ou PDF, roda o pipeline em segundo plano e expõe progresso, resultado e histórico.

Os resultados ficam no banco (armazenamento/): cada geração vira uma execução versionada, e pedir de novo o
mesmo documento com a mesma configuração devolve o resultado guardado, sem chamar os modelos.

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

import yaml

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from armazenamento.repositorio import Repositorio
from armazenamento.servico import processar_com_banco
from avaliador import avaliar as av
from avaliador import glossario
from avaliador.juiz import clientes_groq
from geracao import grafo
from geracao.schemas import FORMATOS
from ingestao import entrada
from ingestao.clientes import ClienteGemini
from ingestao.documento import Documento, ErroIngestao

LIMITE_PDF = 26 * 1024 * 1024
RAIZ = Path(__file__).resolve().parent.parent
PASTA_FRONT = RAIZ / "frontend" / "dist"   # gerada por `npm run build` em frontend/


def clientes_padrao() -> grafo.Clientes:
    """Extrator e juiz na Groq (gpt-oss-120b, ou outro modelo para o juiz via JUIZ_MODELO) e gerador no Gemini."""
    extrator, juiz = clientes_groq()
    return grafo.Clientes(extrator=extrator, gerador=ClienteGemini(), juiz=juiz)


class PedidoJob(BaseModel):
    tipo: Literal["termo", "link"]
    valor: str
    niveis: list[str] = list(av.NIVEIS)
    formatos: list[str] = list(FORMATOS)
    prioritario: str | None = None
    tentativas: int = 3
    concorrencia: int = 2
    sessao: str | None = None
    forcar: bool = False          # ignora o cache e gera de novo


class Cancelado(Exception):
    """Levantada dentro do processamento quando a pessoa cancela: interrompe o grafo na próxima etapa."""


@dataclass
class Job:
    id: str
    entrada: dict
    sessao: str | None = None
    status: str = "ingerindo"            # ingerindo | processando | concluido | erro | cancelado
    eventos: list[dict] = field(default_factory=list)
    resultado: dict | None = None
    erro: str | None = None
    criado_em: float = field(default_factory=time.time)
    cancelado: threading.Event = field(default_factory=threading.Event)

    def publicar(self, evento: dict) -> None:
        self.eventos.append({**evento, "t": round(time.time() - self.criado_em, 1)})


def criar_app(fabrica_clientes: Callable[[], grafo.Clientes] = clientes_padrao,
              ingestor: Callable[..., Documento] | None = None, repositorio: Repositorio | None = None,
              cfg: dict | None = None, pasta_front: Path | None = PASTA_FRONT) -> FastAPI:
    app = FastAPI(title="Suno Content")
    indice = glossario.Indice(glossario.carregar())
    repo = repositorio or Repositorio()
    jobs: dict[str, Job] = {}
    pool = ThreadPoolExecutor(max_workers=2)
    trava = threading.Lock()

    def ingerir(tipo: str, valor: Any, nome: str | None) -> Documento:
        if ingestor is not None:
            return ingestor(tipo, valor, nome, indice)
        if tipo == "termo":
            return entrada.ingerir_termo(valor, indice)
        if tipo == "link":
            return entrada.ingerir_link(valor, indice)
        return entrada.ingerir_pdf(valor, nome or "documento.pdf", indice)

    def executar(job: Job, pedido: PedidoJob, tipo: str, valor: Any, nome: str | None) -> None:
        def observar(evento: dict) -> None:
            if job.cancelado.is_set():
                raise Cancelado()
            job.publicar(evento)

        try:
            job.publicar({"tipo": "ingerindo"})
            doc = ingerir(tipo, valor, nome)
            if job.cancelado.is_set():
                return
            p = doc.proveniencia
            job.publicar({"tipo": "documento", "origem": p.origem, "url": p.url, "palavras": len(doc.texto.split()),
                          "paginas": doc.paginas})
            job.status = "processando"
            proc = processar_com_banco(
                doc, fabrica_clientes(), indice, repo, cfg, niveis=tuple(pedido.niveis), formatos=tuple(pedido.formatos),
                nivel_prioritario=pedido.prioritario, max_tentativas=pedido.tentativas, concorrencia=pedido.concorrencia,
                sessao=job.sessao, forcar=pedido.forcar, observador=observar,
            )
            if job.cancelado.is_set():
                return   # terminou junto com o pedido de cancelamento: a pessoa pediu para parar
            job.resultado = json.loads(proc.model_dump_json())
            job.status = "concluido"
            job.publicar({"tipo": "fim", "execucao": proc.execucao_id, "do_cache": proc.do_cache})
        except Cancelado:
            return          # o status e o evento já foram publicados por quem cancelou
        except ErroIngestao as e:
            if job.cancelado.is_set():
                return
            job.erro, job.status = str(e), "erro"
            job.publicar({"tipo": "erro", "mensagem": job.erro})
        except Exception as e:   # chave ausente, API fora do ar etc.
            if job.cancelado.is_set():
                return
            job.erro, job.status = f"{type(e).__name__}: {str(e)[:300]}", "erro"
            job.publicar({"tipo": "erro", "mensagem": job.erro})

    def abrir(pedido: PedidoJob, tipo: str, valor: Any, nome: str | None, info: dict) -> dict:
        for n in pedido.niveis:
            if n not in av.NIVEIS:
                raise HTTPException(422, f"nível desconhecido: {n}")
        for f in pedido.formatos:
            if f not in FORMATOS:
                raise HTTPException(422, f"formato desconhecido: {f}")
        # PDF enviado é privado: sem sessão informada, cria-se uma e devolve-se ao chamador.
        sessao = pedido.sessao or (uuid.uuid4().hex[:16] if tipo == "pdf" else None)
        job = Job(id=uuid.uuid4().hex[:10], entrada=info, sessao=sessao)
        with trava:
            jobs[job.id] = job
        pool.submit(executar, job, pedido, tipo, valor, nome)
        return {"id": job.id, "sessao": sessao}

    @app.post("/api/jobs")
    def criar_job(pedido: PedidoJob):
        if not pedido.valor.strip():
            raise HTTPException(422, "informe um termo ou um link")
        return abrir(pedido, pedido.tipo, pedido.valor, None, {"tipo": pedido.tipo, "valor": pedido.valor})

    @app.post("/api/jobs/pdf")
    async def criar_job_pdf(request: Request, nome: str = "documento.pdf", niveis: str = ",".join(av.NIVEIS),
                            formatos: str = ",".join(FORMATOS), prioritario: str | None = None,
                            sessao: str | None = None, forcar: bool = False):
        dados = await request.body()
        if len(dados) > LIMITE_PDF:
            raise HTTPException(413, "PDF grande demais")
        pedido = PedidoJob(tipo="termo", valor="-", niveis=niveis.split(","), formatos=formatos.split(","),
                           prioritario=prioritario, sessao=sessao, forcar=forcar)
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

    @app.post("/api/jobs/{job_id}/cancelar")
    def cancelar_job(job_id: str):
        """Para o processamento: o que já está sendo escrito termina sozinho, mas nada novo começa e nada é guardado."""
        j = pegar(job_id)
        if j.status in ("concluido", "erro", "cancelado"):
            return {"id": j.id, "status": j.status}
        j.cancelado.set()
        j.status = "cancelado"
        j.publicar({"tipo": "cancelado"})
        return {"id": j.id, "status": j.status}

    @app.get("/api/jobs/{job_id}/eventos")
    async def eventos(job_id: str):
        j = pegar(job_id)

        async def fluxo():
            enviados = 0
            while True:
                while enviados < len(j.eventos):
                    yield f"data: {json.dumps(j.eventos[enviados], ensure_ascii=False)}\n\n"
                    enviados += 1
                if j.status in ("concluido", "erro", "cancelado") and enviados >= len(j.eventos):
                    return
                await asyncio.sleep(0.4)

        return StreamingResponse(fluxo(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/api/execucoes")
    def listar_execucoes(sessao: str | None = None):
        """Execuções públicas (fontes oficiais) e as da sessão informada."""
        return repo.listar(sessao)

    @app.get("/api/execucoes/{execucao_id}")
    def ver_execucao(execucao_id: str, sessao: str | None = None):
        if not repo.pode_ver(execucao_id, sessao):
            raise HTTPException(404, "execução não encontrada")
        proc = repo.abrir(execucao_id)
        if proc is None:
            raise HTTPException(404, "execução não encontrada")
        return json.loads(proc.model_dump_json())

    @app.get("/api/execucoes/{execucao_id}/relacionados")
    def ver_relacionados(execucao_id: str, sessao: str | None = None):
        """Outros documentos com as mesmas entidades (por exemplo, quem também fala de Selic e IPCA)."""
        if not repo.pode_ver(execucao_id, sessao):
            raise HTTPException(404, "execução não encontrada")
        return repo.relacionados(execucao_id, sessao)

    @app.get("/api/config")
    def configuracao():
        c = cfg or av.carregar_config()
        return {"niveis": list(av.NIVEIS), "formatos": list(FORMATOS), "limiares": c["niveis"], "formato_limites": c["formatos"]}

    with open(glossario.CAMINHO_PADRAO, encoding="utf-8") as f:
        termos_glossario = [
            {"termo": t["termo"], "nivel": t["nivel"], "formas": [t["termo"], *t.get("variantes", [])],
             "explicacao": t["explicacao_curta"], "ambiguo": bool(t.get("ambiguo", False))}
            for t in yaml.safe_load(f)["termos"]
        ]

    @app.get("/api/glossario")
    def ver_glossario():
        """Termos do glossario, para a interface destacar no texto o que e jargao de cada nivel."""
        return termos_glossario

    # A interface compilada (frontend/dist) e servida na raiz, depois das rotas /api.
    if pasta_front is not None and Path(pasta_front).exists():
        app.mount("/", StaticFiles(directory=pasta_front, html=True), name="front")
    return app


app = criar_app()
