export default function Cabecalho({ onInicio }: { onInicio: () => void }) {
  return (
    <header className="cabecalho">
      <div className="miolo">
        <button type="button" className="logo" onClick={onInicio} aria-label="Suno Content, voltar ao início"
          style={{ background: "none", border: 0, padding: 0 }}>
          <span className="par">(</span> SUNO <span className="par">)</span><small>CONTENT</small>
        </button>
      </div>
    </header>
  );
}
