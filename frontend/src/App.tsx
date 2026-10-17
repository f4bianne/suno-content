import { useCallback, useEffect, useRef, useState } from "react";
import { cancelarJob, criarJob, criarJobPdf, listarExecucoes, verConfig, verExecucao, verGlossario, verJob, type Opcoes } from "./api";
import Andamento from "./componentes/Andamento";
import Cabecalho from "./componentes/Cabecalho";
import Entrada, { type Pedido } from "./componentes/Entrada";
import Historico from "./componentes/Historico";
import { chaveCelula } from "./componentes/Mapa";
import Resultado from "./componentes/Resultado";
import type { Config, EstadoCelula, Evento, Processamento, ResumoExecucao, TermoGlossario } from "./tipos";

/** Estado ao vivo de cada um dos 9 conteúdos, derivado dos eventos que o servidor vai enviando. */
export function celulasDosEventos(eventos: Evento[]): Record<string, EstadoCelula> {
  const m: Record<string, EstadoCelula> = {};
  for (const e of eventos) {
    if (!e.nivel || !e.formato) continue;
    const k = chaveCelula(e.nivel, e.formato);
    if (e.tipo === "gerando") m[k] = { fase: "gerando", tentativa: e.tentativa ?? 1 };
    else if (e.tipo === "revisando") m[k] = { fase: "revisando", tentativa: e.tentativa ?? 1 };
    else if (e.tipo === "avaliado") m[k] = { fase: "avaliado", tentativa: e.tentativa ?? 1, aprovado: e.aprovado };
    else if (e.tipo === "ramo_fim") m[k] = { fase: "fim", tentativa: e.tentativas ?? 1, status: e.status };
  }
  return m;
}

type Tela = "inicio" | "gerando" | "resultado";

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [glossario, setGlossario] = useState<TermoGlossario[]>([]);
  const [historico, setHistorico] = useState<ResumoExecucao[]>([]);
  const [tela, setTela] = useState<Tela>("inicio");
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [resultado, setResultado] = useState<Processamento | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [total, setTotal] = useState(9);
  const [aviso, setAviso] = useState<string | null>(null);
  const jobAtual = useRef<string | null>(null);
  const [pedidos, setPedidos] = useState<string[] | undefined>(undefined);
  const fonte = useRef<EventSource | null>(null);

  const recarregarHistorico = useCallback(() => { listarExecucoes().then(setHistorico).catch(() => setHistorico([])); }, []);
  useEffect(() => {
    verConfig().then(setConfig).catch(() => undefined);          // sem as faixas, a tela só não mostra os limites
    verGlossario().then(setGlossario).catch(() => undefined);    // sem o glossário, os termos não são marcados
    recarregarHistorico();
    return () => fonte.current?.close();
  }, [recarregarHistorico]);

  function voltarAoInicio() {
    fonte.current?.close();
    setTela("inicio"); setResultado(null); setEventos([]); setErro(null);
    recarregarHistorico();
  }

  async function gerar(pedido: Pedido, opcoes: Opcoes) {
    fonte.current?.close();
    setErro(null); setAviso(null); setResultado(null); setEventos([]); setTela("gerando");
    setTotal(Math.max(1, opcoes.niveis.length * opcoes.formatos.length));
    setPedidos(opcoes.niveis.flatMap((n) => opcoes.formatos.map((f) => chaveCelula(n, f))));
    try {
      const { id } = pedido.tipo === "pdf" ? await criarJobPdf(pedido.arquivo, opcoes) : await criarJob(pedido.tipo, pedido.valor, opcoes);
      jobAtual.current = id;
      const es = new EventSource(`/api/jobs/${id}/eventos`);
      fonte.current = es;
      es.onmessage = async (m) => {
        const ev: Evento = JSON.parse(m.data);
        if (ev.tipo === "cancelado") { es.close(); return; }
        setEventos((atual) => [...atual, ev]);
        if (ev.tipo !== "fim" && ev.tipo !== "erro") return;
        es.close();
        try {
          const job = await verJob(id);
          if (job.resultado) { setResultado(job.resultado); setTela("resultado"); }
          else { setErro(job.erro ?? "Não foi possível gerar os conteúdos."); setTela("inicio"); }
        } catch (e) { setErro(e instanceof Error ? e.message : String(e)); setTela("inicio"); }
        recarregarHistorico();
      };
      es.onerror = () => {
        es.close();
        setErro((atual) => atual ?? "A conexão com o servidor foi interrompida.");
        setTela((t) => (t === "gerando" ? "inicio" : t));
      };
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
      setTela("inicio");
    }
  }

  /** Para a geração: o servidor não começa nada novo e não guarda o resultado. */
  function cancelar() {
    const id = jobAtual.current;
    fonte.current?.close();
    jobAtual.current = null;
    if (id) cancelarJob(id).catch(() => undefined);   // se o servidor não responder, a tela volta mesmo assim
    setTela("inicio"); setEventos([]); setResultado(null);
    setAviso("Geração cancelada. Nada foi guardado.");
  }

  async function abrir(id: string) {
    try {
      setErro(null);
      setResultado(await verExecucao(id));
      setTela("resultado");
      window.scrollTo({ top: 0 });
    } catch (e) { setErro(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <>
      <Cabecalho onInicio={voltarAoInicio} />
      <main className="miolo pagina">
        {tela === "inicio" && (
          <>
            <Entrada ocupado={false} erro={erro} aviso={aviso} onGerar={gerar} />
            <Historico itens={historico} onAbrir={abrir} />
          </>
        )}
        {tela === "gerando" && <Andamento eventos={eventos} ao_vivo={celulasDosEventos(eventos)} total={total} pedidos={pedidos} onCancelar={cancelar} />}
        {tela === "resultado" && resultado && (
          <Resultado key={resultado.execucao_id ?? resultado.documento_chave} resultado={resultado} config={config} glossario={glossario}
            onNovo={voltarAoInicio} historico={historico} />
        )}
      </main>
    </>
  );
}
