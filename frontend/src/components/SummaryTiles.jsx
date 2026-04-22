export default function SummaryTiles({ summary, loading }) {
  if (loading) {
    return (
      <div className="tiles">
        {[1, 2, 3, 4, 5, 6].map((k) => (
          <div key={k} className="tile tile-skeleton" />
        ))}
        <style>{tileStyles}</style>
      </div>
    )
  }
  if (!summary) return null

  const {
    total_interfaces,
    healthy_count,
    warning_count,
    critical_count,
    anomalies_detected,
    avg_health_score,
  } = summary

  return (
    <div className="tiles fade-in">
      <Tile label="TOTAL IFACES" value={total_interfaces} kind="neutral" />
      <Tile label="HEALTHY" value={healthy_count} kind="healthy" share={healthy_count / total_interfaces} />
      <Tile label="WARNING" value={warning_count} kind="warning" share={warning_count / total_interfaces} />
      <Tile label="CRITICAL" value={critical_count} kind="critical" share={critical_count / total_interfaces} />
      <Tile label="ANOMALIES" value={anomalies_detected} kind="accent" />
      <Tile label="AVG SCORE" value={avg_health_score} suffix="/100" kind={scoreKind(avg_health_score)} />
      <style>{tileStyles}</style>
    </div>
  )
}

function scoreKind(s) {
  if (s >= 80) return 'healthy'
  if (s >= 55) return 'warning'
  return 'critical'
}

function Tile({ label, value, suffix = '', kind = 'neutral', share }) {
  return (
    <div className={`tile tile-${kind}`}>
      <div className="tile-label text-2 uppercase">{label}</div>
      <div className="tile-value-row">
        <span className="tile-value tabular">{value}</span>
        {suffix && <span className="tile-suffix text-2">{suffix}</span>}
      </div>
      {share !== undefined && (
        <div className="tile-bar">
          <div className="tile-bar-fill" style={{ width: `${Math.round(share * 100)}%` }} />
        </div>
      )}
    </div>
  )
}

const tileStyles = `
  .tiles {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: var(--sp-2);
    padding: var(--sp-3) var(--sp-4);
    flex: 0 0 auto;
  }

  .tile {
    position: relative;
    padding: var(--sp-3) var(--sp-4);
    background: var(--bg-1);
    border: 1px solid var(--border-0);
    border-left: 2px solid var(--border-1);
    min-height: 78px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease);
  }

  .tile:hover {
    background: var(--bg-2);
    border-color: var(--border-2);
  }

  .tile-skeleton {
    background: linear-gradient(90deg, var(--bg-1), var(--bg-2), var(--bg-1));
    background-size: 200% 100%;
    animation: skeleton 1.4s ease-in-out infinite;
  }
  @keyframes skeleton {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .tile-label {
    font-size: var(--fs-xs);
    letter-spacing: 0.15em;
  }

  .tile-value-row {
    display: flex;
    align-items: baseline;
    gap: var(--sp-1);
  }

  .tile-value {
    font-family: var(--font-display);
    font-size: var(--fs-2xl);
    font-weight: 600;
    line-height: 1;
    letter-spacing: -0.02em;
  }

  .tile-suffix {
    font-size: var(--fs-sm);
  }

  .tile-bar {
    height: 2px;
    background: var(--bg-3);
    margin-top: var(--sp-2);
    overflow: hidden;
  }

  .tile-bar-fill {
    height: 100%;
    background: currentColor;
    opacity: 0.5;
    transition: width var(--dur-slow) var(--ease);
  }

  .tile-healthy { border-left-color: var(--status-healthy-line); color: var(--status-healthy-fg); }
  .tile-healthy .tile-value { color: var(--status-healthy-fg); }

  .tile-warning { border-left-color: var(--status-warning-line); color: var(--status-warning-fg); }
  .tile-warning .tile-value { color: var(--status-warning-fg); }

  .tile-critical { border-left-color: var(--status-critical-line); color: var(--status-critical-fg); }
  .tile-critical .tile-value { color: var(--status-critical-fg); }

  .tile-accent { border-left-color: var(--accent); color: var(--accent); }
  .tile-accent .tile-value { color: var(--accent); }

  .tile-neutral .tile-value { color: var(--text-0); }

  @media (max-width: 1200px) {
    .tiles { grid-template-columns: repeat(3, 1fr); }
  }
  @media (max-width: 680px) {
    .tiles { grid-template-columns: repeat(2, 1fr); }
  }
`
