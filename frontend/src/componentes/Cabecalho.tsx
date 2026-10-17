import { MARCA_CLARA, MARCA_ESCURA } from "../util/marca";

export default function Cabecalho({ onInicio }: { onInicio: () => void }) {
  return (
    <header className="cabecalho">
      <div className="miolo">
        <button type="button" className="logo" onClick={onInicio} aria-label="Suno Content, voltar ao início"
          style={{ background: "none", border: 0, padding: 0 }}>
          <picture>
            <source srcSet={MARCA_ESCURA} media="(prefers-color-scheme: dark)" />
            <img src={MARCA_CLARA} alt="" />
          </picture>
          <small>CONTENT</small>
        </button>
      </div>
    </header>
  );
}
