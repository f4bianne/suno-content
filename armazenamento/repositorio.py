"""Repositorio: salva e le documentos, execucoes (versoes), ramos e tentativas (itens 20 e 22).

Cada geracao vira uma execucao nova; nada e substituido. O cache so reaproveita uma execucao quando o
documento e a configuracao completa (modelos, prompts, glossario, regras, codigo) sao os mesmos.
Escopo: documento vindo de fonte oficial (termo ou link) e `publico`; PDF enviado e `sessao` e so aparece
para a sessao que o enviou.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, MetaData, String, Table, Text,
                        UniqueConstraint, create_engine, func, select)
from sqlalchemy.pool import StaticPool

from avaliador.ancora import Ancora
from geracao.grafo import Processamento
from geracao.ramo import ResultadoRamo, Tentativa
from ingestao.documento import Documento

RAIZ = Path(__file__).resolve().parent.parent
URL_PADRAO = f"sqlite:///{(RAIZ / 'dados' / 'suno.db').as_posix()}"

metadata = MetaData()
documentos = Table(
    "documentos", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("chave", String(64), nullable=False),              # hash do texto normalizado
    Column("escopo", String(10), nullable=False),             # publico | sessao
    Column("sessao", String(64), nullable=False, default=""),
    Column("tipo", String(10), nullable=False),               # termo | link | pdf
    Column("origem", Text, nullable=False),
    Column("url", Text),
    Column("sha256_bruto", String(64), nullable=False),
    Column("paginas", Integer),
    Column("palavras", Integer, nullable=False),
    Column("coletado_em", DateTime(timezone=True), nullable=False),
    Column("texto", Text, nullable=False),
    UniqueConstraint("chave", "escopo", "sessao", name="uq_documento"),
)
execucoes = Table(
    "execucoes", metadata,
    Column("id", String(16), primary_key=True),
    Column("documento_id", Integer, ForeignKey("documentos.id"), nullable=False),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("config_hash", String(16), nullable=False),
    Column("config", JSON, nullable=False),
    Column("niveis", JSON, nullable=False),
    Column("formatos", JSON, nullable=False),
    Column("ancora", JSON, nullable=False),
    Column("descartados", JSON, nullable=False),
    Column("segundos", Float, nullable=False, default=0.0),
    Index("ix_exec_cache", "documento_id", "config_hash"),
)
ramos = Table(
    "ramos", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("execucao_id", String(16), ForeignKey("execucoes.id"), nullable=False),
    Column("nivel", String(20), nullable=False),
    Column("formato", String(12), nullable=False),
    Column("status", String(12), nullable=False),
    Column("conteudo", JSON),
)
tentativas = Table(
    "tentativas", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ramo_id", Integer, ForeignKey("ramos.id"), nullable=False),
    Column("n", Integer, nullable=False),
    Column("aprovado", Boolean, nullable=False),
    Column("falhas", JSON, nullable=False),
    Column("metricas", JSON, nullable=False),
    Column("veredito", JSON),
    Column("conteudo", JSON),
    Column("segundos_geracao", Float, nullable=False),
    Column("segundos_avaliacao", Float, nullable=False),
    Column("chamadas_llm", Integer, nullable=False),
)


acessos = Table(
    "acessos", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("documento_id", Integer, ForeignKey("documentos.id"), nullable=False),
    Column("acerto", Boolean, nullable=False),            # True = veio do cache, sem chamar modelos
    Column("execucao_id", String(16), ForeignKey("execucoes.id"), nullable=False),
)


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


class Repositorio:
    def __init__(self, url: str = URL_PADRAO):
        kwargs: dict = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool   # um banco em memoria por conexao: reaproveita a mesma
        if url.startswith("sqlite:///") and not url.endswith(":memory:"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, **kwargs)
        metadata.create_all(self.engine)

    # ---------- documentos ----------

    @staticmethod
    def _escopo(doc: Documento, sessao: str | None) -> tuple[str, str]:
        return ("sessao", sessao or "") if doc.proveniencia.tipo == "pdf" else ("publico", "")

    def salvar_documento(self, doc: Documento, sessao: str | None = None) -> int:
        escopo, sess = self._escopo(doc, sessao)
        p = doc.proveniencia
        with self.engine.begin() as c:
            achado = c.execute(select(documentos.c.id).where(
                documentos.c.chave == doc.chave, documentos.c.escopo == escopo, documentos.c.sessao == sess)).scalar()
            if achado:
                return achado
            r = c.execute(documentos.insert().values(
                chave=doc.chave, escopo=escopo, sessao=sess, tipo=p.tipo, origem=p.origem, url=p.url,
                sha256_bruto=p.sha256_bruto, paginas=doc.paginas, palavras=len(doc.texto.split()),
                coletado_em=p.coletado_em, texto=doc.texto))
            return r.inserted_primary_key[0]

    def url_conhecida(self, url: str) -> bool:
        """Para o monitor: essa fonte oficial ja foi baixada antes?"""
        with self.engine.connect() as c:
            return c.execute(select(func.count()).select_from(documentos).where(
                documentos.c.url == url, documentos.c.escopo == "publico")).scalar() > 0

    # ---------- acessos (taxa de acerto do cache) ----------

    def registrar_acesso(self, documento_id: int, acerto: bool, execucao_id: str) -> None:
        with self.engine.begin() as c:
            c.execute(acessos.insert().values(criado_em=datetime.now(timezone.utc), documento_id=documento_id,
                                              acerto=acerto, execucao_id=execucao_id))

    def taxa_de_cache(self) -> tuple[int, int]:
        """(acertos, total de pedidos) desde que os acessos passaram a ser registrados."""
        with self.engine.connect() as c:
            total = c.execute(select(func.count()).select_from(acessos)).scalar()
            acertos = c.execute(select(func.count()).select_from(acessos).where(acessos.c.acerto.is_(True))).scalar()
        return acertos, total

    # ---------- execucoes ----------

    def buscar_cache(self, documento_id: int, config_hash: str, niveis: list[str], formatos: list[str]) -> str | None:
        """Execucao mais recente com o mesmo documento e a mesma configuracao que cobre o que foi pedido."""
        with self.engine.connect() as c:
            linhas = c.execute(select(execucoes.c.id, execucoes.c.niveis, execucoes.c.formatos).where(
                execucoes.c.documento_id == documento_id, execucoes.c.config_hash == config_hash,
            ).order_by(execucoes.c.criado_em.desc())).all()
        for id_, ns, fs in linhas:
            if set(niveis) <= set(ns) and set(formatos) <= set(fs):
                return id_
        return None

    def salvar_execucao(self, documento_id: int, proc: Processamento, config: dict, config_hash: str,
                        niveis: list[str], formatos: list[str], segundos: float) -> str:
        id_ = uuid.uuid4().hex[:12]
        with self.engine.begin() as c:
            c.execute(execucoes.insert().values(
                id=id_, documento_id=documento_id, criado_em=_utc(proc.gerado_em), config_hash=config_hash, config=config,
                niveis=niveis, formatos=formatos, ancora=proc.ancora.model_dump(mode="json"),
                descartados=[list(x) for x in proc.fatos_descartados], segundos=segundos))
            for r in proc.ramos:
                ramo_id = c.execute(ramos.insert().values(
                    execucao_id=id_, nivel=r.nivel, formato=r.formato, status=r.status, conteudo=r.conteudo)).inserted_primary_key[0]
                for t in r.tentativas:
                    c.execute(tentativas.insert().values(
                        ramo_id=ramo_id, n=t.n, aprovado=t.aprovado, falhas=t.falhas, metricas=t.metricas, veredito=t.veredito,
                        conteudo=t.conteudo, segundos_geracao=t.segundos_geracao, segundos_avaliacao=t.segundos_avaliacao,
                        chamadas_llm=t.chamadas_llm))
        return id_

    def abrir(self, execucao_id: str, niveis: list[str] | None = None, formatos: list[str] | None = None,
              do_cache: bool = False) -> Processamento | None:
        with self.engine.connect() as c:
            e = c.execute(select(execucoes, documentos.c.chave, documentos.c.origem, documentos.c.url)
                          .join(documentos, documentos.c.id == execucoes.c.documento_id)
                          .where(execucoes.c.id == execucao_id)).mappings().first()
            if e is None:
                return None
            lista = []
            for r in c.execute(select(ramos).where(ramos.c.execucao_id == execucao_id).order_by(ramos.c.id)).mappings():
                if (niveis and r["nivel"] not in niveis) or (formatos and r["formato"] not in formatos):
                    continue
                ts = c.execute(select(tentativas).where(tentativas.c.ramo_id == r["id"]).order_by(tentativas.c.id)).mappings().all()
                lista.append(ResultadoRamo(
                    nivel=r["nivel"], formato=r["formato"], status=r["status"], conteudo=r["conteudo"],
                    tentativas=[Tentativa(n=t["n"], aprovado=t["aprovado"], falhas=t["falhas"], metricas=t["metricas"],
                                          veredito=t["veredito"], conteudo=t["conteudo"], segundos_geracao=t["segundos_geracao"],
                                          segundos_avaliacao=t["segundos_avaliacao"], chamadas_llm=t["chamadas_llm"]) for t in ts]))
        return Processamento(
            gerado_em=_utc(e["criado_em"]), execucao_id=execucao_id, do_cache=do_cache, config=e["config"],
            documento_chave=e["chave"], origem=e["origem"], url=e["url"], ancora=Ancora.model_validate(e["ancora"]),
            fatos_descartados=[tuple(x) for x in e["descartados"]], ramos=lista)

    def listar(self, sessao: str | None = None, limite: int = 100) -> list[dict]:
        """Execucoes publicas e as da sessao informada, da mais recente para a mais antiga."""
        with self.engine.connect() as c:
            q = (select(execucoes.c.id, execucoes.c.criado_em, execucoes.c.config, execucoes.c.segundos, documentos.c.origem,
                        documentos.c.url, documentos.c.tipo, documentos.c.escopo, documentos.c.chave)
                 .join(documentos, documentos.c.id == execucoes.c.documento_id)
                 .order_by(execucoes.c.criado_em.desc()).limit(limite))
            q = q.where((documentos.c.escopo == "publico") | ((documentos.c.escopo == "sessao") & (documentos.c.sessao == (sessao or "_"))))
            linhas = c.execute(q).mappings().all()
            saida = []
            for e in linhas:
                status = [s for (s,) in c.execute(select(ramos.c.status).where(ramos.c.execucao_id == e["id"]))]
                saida.append({"id": e["id"], "documento": e["chave"], "origem": e["origem"], "url": e["url"], "tipo": e["tipo"], "escopo": e["escopo"],
                              "criado_em": _utc(e["criado_em"]).isoformat(), "ramos": len(status),
                              "aprovados": status.count("aprovado"), "modelos": e["config"].get("modelos"),
                              "segundos": round(e["segundos"], 1)})
            return saida

    def relacionados(self, execucao_id: str, sessao: str | None = None, limite: int = 3) -> list[dict]:
        """Outros documentos que falam das mesmas coisas, pelas entidades dos fatos extraidos (Jaccard).

        Considera so o que a sessao pode ver, uma execucao (a mais recente) por documento, e ignora o proprio documento.
        """
        def entidades(ancora: dict) -> dict[str, str]:
            return {e.strip().casefold(): e.strip() for f in ancora.get("fatos", []) for e in f.get("entidades", []) if e.strip()}

        with self.engine.connect() as c:
            alvo = c.execute(select(execucoes.c.documento_id, execucoes.c.ancora).where(execucoes.c.id == execucao_id)).first()
            if alvo is None:
                return []
            minhas = entidades(alvo[1])
            q = (select(execucoes.c.id, execucoes.c.documento_id, execucoes.c.criado_em, execucoes.c.ancora, documentos.c.origem)
                 .join(documentos, documentos.c.id == execucoes.c.documento_id)
                 .where(execucoes.c.documento_id != alvo[0])
                 .where((documentos.c.escopo == "publico") | ((documentos.c.escopo == "sessao") & (documentos.c.sessao == (sessao or "_"))))
                 .order_by(execucoes.c.criado_em.desc()))
            outras = c.execute(q).mappings().all()
            vistos: set[int] = set()
            achados = []
            for o in outras:
                if o["documento_id"] in vistos:
                    continue
                vistos.add(o["documento_id"])
                dela = entidades(o["ancora"])
                comuns = sorted(minhas.keys() & dela.keys())
                if not comuns:
                    continue
                uniao = len(minhas.keys() | dela.keys())
                status = [s for (s,) in c.execute(select(ramos.c.status).where(ramos.c.execucao_id == o["id"]))]
                achados.append({"id": o["id"], "origem": o["origem"], "criado_em": _utc(o["criado_em"]).isoformat(),
                                "ramos": len(status), "aprovados": status.count("aprovado"),
                                "entidades_comuns": [minhas[k] for k in comuns], "afinidade": round(len(comuns) / uniao, 3)})
        achados.sort(key=lambda a: (-a["afinidade"], -len(a["entidades_comuns"])))
        return achados[:limite]

    def pode_ver(self, execucao_id: str, sessao: str | None) -> bool:
        with self.engine.connect() as c:
            d = c.execute(select(documentos.c.escopo, documentos.c.sessao).join(
                execucoes, execucoes.c.documento_id == documentos.c.id).where(execucoes.c.id == execucao_id)).first()
        return d is not None and (d[0] == "publico" or d[1] == (sessao or "_"))
