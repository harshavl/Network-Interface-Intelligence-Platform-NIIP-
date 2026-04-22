import { AlertTriangle, Wrench, TrendingUp, Activity, X } from 'lucide-react'

export default function InterfaceDetail({ iface, onClose }) {
  if (!iface) {
    return (
      <aside className="detail detail-empty">
        <div className="detail-placeholder">
          <Activity size={24} className="text-3" />
          <div className="text-2 uppercase" style={{ fontSize: 'var(--fs-xs)', letterSpacing: '0.15em' }}>
            SELECT AN INTERFACE
          </div>
          <div className="text-3" style={{ fontSize: 'var(--fs-xs)' }}>
            Click any row to inspect details, anomalies, forecast, and recommended actions.
          </div>
        </div>
        <style>{styles}</style>
      </aside>
    )
  }

  return (
    <aside className={`detail status-bg-${iface.status} fade-in`}>
      <header className="detail-head">
        <div>
          <div className="detail-breadcrumb text-2 uppercase">
            {iface.device}
          </div>
          <div className="detail-title">{iface.interface}</div>
          {iface.description && (
            <div className="detail-desc text-2">{iface.description}</div>
          )}
        </div>
        <button className="close-btn" onClick={onClose} aria-label="Close">
          <X size={14} />
        </button>
      </header>

      <div className="detail-score-row">
        <ScoreRing score={iface.health_score} status={iface.status} />
        <StatusBadge status={iface.status} />
      </div>

      <div className="detail-body">
        <Section
          icon={<AlertTriangle size={13} />}
          title="ANOMALIES"
          count={iface.anomalies?.length || 0}
        >
          {iface.anomalies && iface.anomalies.length > 0 ? (
            <div className="anomaly-list">
              {iface.anomalies.map((a, i) => (
                <AnomalyItem key={i} anomaly={a} />
              ))}
            </div>
          ) : (
            <div className="empty text-3">No anomalies detected.</div>
          )}
        </Section>

        {iface.forecast && (
          <Section icon={<TrendingUp size={13} />} title="FORECAST">
            <ForecastBlock forecast={iface.forecast} />
          </Section>
        )}

        {iface.root_cause_suggestion && (
          <Section icon={<Wrench size={13} />} title="ROOT CAUSE">
            <RootCauseBlock rc={iface.root_cause_suggestion} />
          </Section>
        )}

        {iface.recommended_actions && iface.recommended_actions.length > 0 && (
          <Section title="RECOMMENDED ACTIONS">
            <ol className="action-list">
              {iface.recommended_actions.map((a, i) => (
                <li key={i}>
                  <span className="action-num text-3">{String(i + 1).padStart(2, '0')}</span>
                  <span className="action-text text-1">{a}</span>
                </li>
              ))}
            </ol>
          </Section>
        )}
      </div>

      <style>{styles}</style>
    </aside>
  )
}

function Section({ icon, title, count, children }) {
  return (
    <section className="section">
      <header className="section-head">
        {icon && <span className="section-icon">{icon}</span>}
        <span className="section-title text-2 uppercase">{title}</span>
        {count !== undefined && (
          <span className="section-count text-3 tabular">[{count}]</span>
        )}
      </header>
      <div className="section-body">{children}</div>
    </section>
  )
}

function ScoreRing({ score, status }) {
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const progress = (score / 100) * circumference
  return (
    <div className="ring-wrap">
      <svg width="72" height="72" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r={radius} fill="none" stroke="var(--border-1)" strokeWidth="3" />
        <circle
          cx="36" cy="36" r={radius}
          fill="none"
          stroke={`var(--status-${status}-fg)`}
          strokeWidth="3"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          transform="rotate(-90 36 36)"
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 500ms var(--ease)' }}
        />
      </svg>
      <div className="ring-label">
        <span className={`ring-score status-${status}`}>{score}</span>
        <span className="ring-max text-3">/100</span>
      </div>
    </div>
  )
}

function StatusBadge({ status }) {
  return (
    <div className={`status-badge status-badge-${status}`}>
      <span className="status-badge-dot" />
      <span>{status.toUpperCase()}</span>
    </div>
  )
}

function AnomalyItem({ anomaly }) {
  return (
    <div className="anomaly">
      <span className={`sev-dot sev-${anomaly.severity}`} />
      <div className="anomaly-body">
        <div className="anomaly-meta">
          <span className={`sev-tag sev-tag-${anomaly.severity} uppercase`}>{anomaly.severity}</span>
          <span className="text-3 uppercase" style={{ fontSize: 'var(--fs-xs)' }}>
            {anomaly.type?.replace(/_/g, ' ')}
          </span>
        </div>
        <div className="anomaly-desc text-1">{anomaly.description}</div>
      </div>
    </div>
  )
}

function ForecastBlock({ forecast }) {
  const breached = forecast.predicted_80pct_breach === 'ALREADY_BREACHED'
  const trendCls = breached ? 'critical' : forecast.trend === 'critical' ? 'critical' : forecast.trend === 'increasing' ? 'warning' : 'text-1'

  return (
    <div className="forecast-grid">
      <div>
        <div className="forecast-label text-3 uppercase">80% BREACH</div>
        <div className={`forecast-value ${breached ? 'critical' : 'text-0'}`}>
          {breached ? 'BREACHED' : forecast.predicted_80pct_breach || '—'}
        </div>
      </div>
      <div>
        <div className="forecast-label text-3 uppercase">DAYS LEFT</div>
        <div className={`forecast-value ${breached ? 'critical' : 'text-0'} tabular`}>
          {forecast.days_until_capacity !== null && forecast.days_until_capacity !== undefined
            ? forecast.days_until_capacity
            : '—'}
        </div>
      </div>
      <div>
        <div className="forecast-label text-3 uppercase">TREND</div>
        <div className={`forecast-value ${trendCls} uppercase`}>{forecast.trend}</div>
      </div>
      <div>
        <div className="forecast-label text-3 uppercase">CONFIDENCE</div>
        <div className="forecast-value text-1 tabular">
          {Math.round((forecast.confidence || 0) * 100)}%
        </div>
      </div>
    </div>
  )
}

function RootCauseBlock({ rc }) {
  const confPct = Math.round((rc.confidence || 0) * 100)
  const confCls = confPct >= 80 ? 'healthy' : confPct >= 60 ? 'warning' : 'critical'
  return (
    <div className="rc-block">
      <div className="rc-header">
        <span className="rc-cause text-0">{rc.probable_cause}</span>
        <span className={`rc-conf ${confCls} tabular`}>{confPct}%</span>
      </div>
      <div className="rc-details text-1">{rc.details}</div>
    </div>
  )
}

const styles = `
  .detail {
    display: flex;
    flex-direction: column;
    background: var(--bg-1);
    border: 1px solid var(--border-0);
    height: 100%;
    min-height: 0;
    overflow: hidden;
    position: relative;
  }

  .detail::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--border-1);
    z-index: 2;
  }
  .status-bg-critical::before { background: var(--status-critical-fg); }
  .status-bg-warning::before  { background: var(--status-warning-fg); }
  .status-bg-healthy::before  { background: var(--status-healthy-fg); }

  .detail-empty {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .detail-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--sp-3);
    max-width: 240px;
    text-align: center;
    padding: var(--sp-6);
  }

  .detail-head {
    padding: var(--sp-4);
    padding-top: calc(var(--sp-4) + 2px);
    border-bottom: 1px solid var(--border-1);
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--sp-3);
    flex: 0 0 auto;
  }
  .detail-breadcrumb {
    font-size: var(--fs-xs);
    letter-spacing: 0.15em;
  }
  .detail-title {
    font-family: var(--font-display);
    font-size: var(--fs-xl);
    font-weight: 600;
    color: var(--text-0);
    line-height: 1.1;
    margin-top: 2px;
    letter-spacing: -0.01em;
  }
  .detail-desc {
    font-size: var(--fs-sm);
    margin-top: var(--sp-1);
  }
  .close-btn {
    padding: var(--sp-1);
    color: var(--text-2);
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-1);
    transition: all var(--dur-fast) var(--ease);
  }
  .close-btn:hover { color: var(--text-0); border-color: var(--text-2); }

  .detail-score-row {
    padding: var(--sp-4);
    display: flex;
    align-items: center;
    gap: var(--sp-4);
    border-bottom: 1px solid var(--border-1);
    flex: 0 0 auto;
  }

  .ring-wrap {
    position: relative;
    width: 72px;
    height: 72px;
  }
  .ring-label {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0;
  }
  .ring-score {
    font-family: var(--font-display);
    font-size: var(--fs-xl);
    font-weight: 600;
    line-height: 1;
  }
  .ring-max { font-size: 9px; line-height: 1; margin-top: 1px; }
  .ring-score.status-healthy { color: var(--status-healthy-fg); }
  .ring-score.status-warning { color: var(--status-warning-fg); }
  .ring-score.status-critical { color: var(--status-critical-fg); }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-2);
    padding: 4px var(--sp-2);
    font-size: var(--fs-xs);
    font-weight: 600;
    letter-spacing: 0.15em;
    border: 1px solid currentColor;
  }
  .status-badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }
  .status-badge-critical { color: var(--status-critical-fg); background: var(--status-critical-bg); }
  .status-badge-warning  { color: var(--status-warning-fg); background: var(--status-warning-bg); }
  .status-badge-healthy  { color: var(--status-healthy-fg); background: var(--status-healthy-bg); }

  .detail-body {
    flex: 1;
    overflow: auto;
    padding: var(--sp-3) var(--sp-4);
    min-height: 0;
  }

  .section {
    padding: var(--sp-3) 0;
    border-bottom: 1px dashed var(--border-0);
  }
  .section:last-child { border-bottom: none; }

  .section-head {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    margin-bottom: var(--sp-2);
  }
  .section-icon {
    color: var(--text-2);
    display: flex;
  }
  .section-title {
    font-size: var(--fs-xs);
    letter-spacing: 0.15em;
  }
  .section-count {
    font-size: var(--fs-xs);
    margin-left: auto;
  }

  .empty { padding: var(--sp-2) 0; font-size: var(--fs-sm); }

  .anomaly-list {
    display: flex;
    flex-direction: column;
    gap: var(--sp-2);
  }
  .anomaly {
    display: flex;
    gap: var(--sp-3);
    padding: var(--sp-2);
    background: var(--bg-2);
    border-left: 2px solid var(--border-1);
  }
  .sev-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-top: 7px;
    flex-shrink: 0;
  }
  .sev-low { background: var(--sev-low); }
  .sev-medium { background: var(--sev-medium); }
  .sev-high { background: var(--sev-high); }
  .sev-critical { background: var(--sev-critical); box-shadow: 0 0 4px var(--sev-critical); }

  .anomaly-body { flex: 1; min-width: 0; }
  .anomaly-meta {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    margin-bottom: var(--sp-1);
  }
  .sev-tag {
    font-size: var(--fs-xs);
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 1px 4px;
  }
  .sev-tag-low      { color: var(--sev-low); }
  .sev-tag-medium   { color: var(--sev-medium); }
  .sev-tag-high     { color: var(--sev-high); }
  .sev-tag-critical { color: var(--sev-critical); }
  .anomaly-desc {
    font-size: var(--fs-sm);
    line-height: var(--lh-loose);
  }

  .forecast-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--sp-3);
  }
  .forecast-label {
    font-size: 9px;
    letter-spacing: 0.15em;
    margin-bottom: 2px;
  }
  .forecast-value {
    font-family: var(--font-display);
    font-size: var(--fs-md);
    font-weight: 600;
    letter-spacing: -0.01em;
  }

  .rc-block {
    padding: var(--sp-3);
    background: var(--bg-2);
    border-left: 2px solid var(--accent);
  }
  .rc-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--sp-3);
    margin-bottom: var(--sp-2);
  }
  .rc-cause {
    font-family: var(--font-display);
    font-size: var(--fs-md);
    font-weight: 600;
    flex: 1;
    letter-spacing: -0.01em;
  }
  .rc-conf {
    font-size: var(--fs-sm);
    font-weight: 600;
  }
  .rc-details {
    font-size: var(--fs-sm);
    line-height: var(--lh-loose);
  }

  .action-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--sp-2);
    padding: 0;
    counter-reset: action;
  }
  .action-list li {
    display: flex;
    gap: var(--sp-3);
    padding: var(--sp-2);
    background: var(--bg-2);
    border-left: 2px solid var(--border-1);
  }
  .action-num {
    font-size: var(--fs-xs);
    font-weight: 600;
    letter-spacing: 0.1em;
    padding-top: 1px;
    flex-shrink: 0;
  }
  .action-text {
    font-size: var(--fs-sm);
    line-height: var(--lh-loose);
  }
`
