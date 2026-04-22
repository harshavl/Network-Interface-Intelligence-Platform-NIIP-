import { useMemo, useState } from 'react'
import { Search, ArrowUp, ArrowDown, Filter } from 'lucide-react'

const STATUS_ORDER = { critical: 0, warning: 1, healthy: 2, unknown: 3 }

const FILTER_OPTIONS = [
  { value: 'all', label: 'ALL' },
  { value: 'critical', label: 'CRITICAL' },
  { value: 'warning', label: 'WARNING' },
  { value: 'healthy', label: 'HEALTHY' },
  { value: 'anomalies', label: 'HAS ANOMALIES' },
]

export default function FleetGrid({ interfaces, selectedId, onSelect }) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [sortBy, setSortBy] = useState('status')
  const [sortDir, setSortDir] = useState('asc')

  const filtered = useMemo(() => {
    if (!interfaces) return []
    let rows = interfaces

    if (filter === 'anomalies') {
      rows = rows.filter((i) => i.anomalies && i.anomalies.length > 0)
    } else if (filter !== 'all') {
      rows = rows.filter((i) => i.status === filter)
    }

    if (query) {
      const q = query.toLowerCase()
      rows = rows.filter(
        (i) =>
          i.device.toLowerCase().includes(q) ||
          i.interface.toLowerCase().includes(q) ||
          (i.description || '').toLowerCase().includes(q),
      )
    }

    const sign = sortDir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      let cmp = 0
      if (sortBy === 'status') {
        cmp = STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
        if (cmp === 0) cmp = a.health_score - b.health_score
      } else if (sortBy === 'score') {
        cmp = a.health_score - b.health_score
      } else if (sortBy === 'anomalies') {
        cmp = (a.anomalies?.length || 0) - (b.anomalies?.length || 0)
      } else if (sortBy === 'device') {
        cmp = a.device.localeCompare(b.device)
      } else if (sortBy === 'interface') {
        cmp = a.interface.localeCompare(b.interface)
      }
      return cmp * sign
    })
  }, [interfaces, filter, query, sortBy, sortDir])

  const toggleSort = (col) => {
    if (sortBy === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(col)
      setSortDir('asc')
    }
  }

  return (
    <section className="fleet">
      <header className="fleet-head">
        <div className="fleet-title">
          <span className="text-2 uppercase">FLEET</span>
          <span className="text-3">·</span>
          <span className="text-1 tabular">{filtered.length} / {interfaces?.length ?? 0}</span>
        </div>

        <div className="fleet-controls">
          <div className="search">
            <Search size={12} className="text-2" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search device, interface, description"
              aria-label="Search"
            />
          </div>

          <div className="filter-group">
            <Filter size={12} className="text-2" />
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={`filter-chip ${filter === opt.value ? 'active' : ''}`}
                onClick={() => setFilter(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="fleet-table-wrap">
        <table className="fleet-table">
          <thead>
            <tr>
              <Th col="status" label="STATUS" {...{ sortBy, sortDir, toggleSort }} width="108" />
              <Th col="score" label="SCORE" {...{ sortBy, sortDir, toggleSort }} width="80" align="right" />
              <Th col="device" label="DEVICE" {...{ sortBy, sortDir, toggleSort }} />
              <Th col="interface" label="INTERFACE" {...{ sortBy, sortDir, toggleSort }} />
              <Th col={null} label="DESCRIPTION" />
              <Th col={null} label="UTIL IN/OUT" align="right" width="120" />
              <Th col={null} label="ERR" align="right" width="56" />
              <Th col={null} label="DISC" align="right" width="64" />
              <Th col="anomalies" label="ANOM" {...{ sortBy, sortDir, toggleSort }} align="right" width="60" />
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan="9" className="empty-row text-2">
                  No interfaces match the current filter.
                </td>
              </tr>
            )}
            {filtered.map((iface) => (
              <Row
                key={`${iface.device}__${iface.interface}`}
                iface={iface}
                selected={selectedId === `${iface.device}__${iface.interface}`}
                onSelect={() => onSelect(iface)}
              />
            ))}
          </tbody>
        </table>
      </div>

      <style>{styles}</style>
    </section>
  )
}

function Th({ col, label, sortBy, sortDir, toggleSort, align = 'left', width }) {
  const sortable = !!col && !!toggleSort
  const active = sortable && sortBy === col
  return (
    <th
      className={`${sortable ? 'sortable' : ''} ${active ? 'active' : ''}`}
      style={{ textAlign: align, width: width ? `${width}px` : undefined }}
      onClick={sortable ? () => toggleSort(col) : undefined}
    >
      <span className="th-inner" style={{ justifyContent: align === 'right' ? 'flex-end' : 'flex-start' }}>
        {label}
        {active && (sortDir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
      </span>
    </th>
  )
}

function Row({ iface, selected, onSelect }) {
  const utilMax = Math.max(
    iface.raw_metrics?.in_utilization_percent ?? 0,
    iface.raw_metrics?.out_utilization_percent ?? 0,
  )
  // Backend omits raw_metrics; if missing, show score-derived util approximation from health
  // (we don't actually need the raw util for display quality, we have the core fields below)
  return (
    <tr
      className={`row status-${iface.status} ${selected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <td>
        <StatusCell status={iface.status} />
      </td>
      <td className="tabular" style={{ textAlign: 'right' }}>
        <ScoreCell score={iface.health_score} status={iface.status} />
      </td>
      <td className="text-0">{iface.device}</td>
      <td className="text-1">{iface.interface}</td>
      <td className="text-2 truncate">{iface.description || '—'}</td>
      <td className="tabular" style={{ textAlign: 'right' }}>
        <UtilCell iface={iface} />
      </td>
      <td className="tabular" style={{ textAlign: 'right' }}>
        <CountCell value={totalErrors(iface)} accent="warning" />
      </td>
      <td className="tabular" style={{ textAlign: 'right' }}>
        <CountCell value={totalDiscards(iface)} accent="warning" />
      </td>
      <td className="tabular" style={{ textAlign: 'right' }}>
        <AnomaliesCell anomalies={iface.anomalies || []} />
      </td>
    </tr>
  )
}

function StatusCell({ status }) {
  return (
    <div className="status-cell">
      <span className={`status-dot status-dot-${status}`} aria-hidden />
      <span className={`status-label status-label-${status} uppercase`}>{status}</span>
    </div>
  )
}

function ScoreCell({ score, status }) {
  return (
    <span className={`score score-${status}`}>
      <span className="score-num">{score}</span>
      <span className="score-max text-3">/100</span>
    </span>
  )
}

function UtilCell({ iface }) {
  // When raw_metrics is present use it; otherwise show health-derived hint
  const inUtil = iface.raw_metrics?.in_utilization_percent
  const outUtil = iface.raw_metrics?.out_utilization_percent
  if (inUtil == null || outUtil == null) return <span className="text-3">—</span>
  return (
    <span>
      <span className={pctClass(inUtil)}>{inUtil.toFixed(0)}%</span>
      <span className="text-3"> / </span>
      <span className={pctClass(outUtil)}>{outUtil.toFixed(0)}%</span>
    </span>
  )
}

function pctClass(p) {
  if (p >= 90) return 'critical'
  if (p >= 70) return 'warning'
  return 'text-1'
}

function CountCell({ value, accent = 'text-2' }) {
  if (!value) return <span className="text-3">0</span>
  const severe = value >= 100
  const cls = severe ? 'critical' : value >= 10 ? 'warning' : 'text-1'
  return <span className={cls}>{value}</span>
}

function AnomaliesCell({ anomalies }) {
  if (!anomalies.length) return <span className="text-3">—</span>
  const severities = anomalies.map((a) => a.severity)
  const hasCritical = severities.includes('critical')
  const hasHigh = severities.includes('high')
  const cls = hasCritical || hasHigh ? 'critical' : 'warning'
  return <span className={cls}>×{anomalies.length}</span>
}

function totalErrors(iface) {
  const m = iface.raw_metrics
  if (!m) return null
  return (m.in_errors_1h || 0) + (m.out_errors_1h || 0)
}
function totalDiscards(iface) {
  const m = iface.raw_metrics
  if (!m) return null
  return (m.in_discards_1h || 0) + (m.out_discards_1h || 0)
}

const styles = `
  .fleet {
    display: flex;
    flex-direction: column;
    background: var(--bg-1);
    border: 1px solid var(--border-0);
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }

  .fleet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--sp-3) var(--sp-4);
    border-bottom: 1px solid var(--border-1);
    gap: var(--sp-4);
    flex: 0 0 auto;
  }
  .fleet-title {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    font-size: var(--fs-xs);
    letter-spacing: 0.15em;
    white-space: nowrap;
  }

  .fleet-controls {
    display: flex;
    align-items: center;
    gap: var(--sp-3);
    flex: 1;
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .search {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    padding: 4px var(--sp-2);
    background: var(--bg-0);
    border: 1px solid var(--border-1);
    min-width: 280px;
  }
  .search input {
    background: none;
    border: none;
    outline: none;
    color: var(--text-0);
    width: 100%;
    font-size: var(--fs-sm);
  }
  .search input::placeholder { color: var(--text-3); }
  .search:focus-within { border-color: var(--accent); }

  .filter-group {
    display: flex;
    align-items: center;
    gap: var(--sp-1);
  }
  .filter-chip {
    padding: 4px var(--sp-2);
    font-size: var(--fs-xs);
    letter-spacing: 0.1em;
    color: var(--text-2);
    background: transparent;
    border: 1px solid var(--border-1);
    transition: all var(--dur-fast) var(--ease);
  }
  .filter-chip:hover { color: var(--text-0); border-color: var(--text-2); }
  .filter-chip.active {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--accent-glow);
  }

  .fleet-table-wrap {
    flex: 1;
    overflow: auto;
    min-height: 0;
  }

  .fleet-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-sm);
  }

  .fleet-table thead {
    position: sticky;
    top: 0;
    background: var(--bg-1);
    z-index: 1;
  }

  .fleet-table th {
    text-align: left;
    padding: var(--sp-2) var(--sp-3);
    font-size: var(--fs-xs);
    font-weight: 500;
    letter-spacing: 0.15em;
    color: var(--text-2);
    border-bottom: 1px solid var(--border-1);
    white-space: nowrap;
    user-select: none;
  }
  .fleet-table th.sortable { cursor: pointer; }
  .fleet-table th.sortable:hover { color: var(--text-0); }
  .fleet-table th.active { color: var(--accent); }
  .th-inner {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-1);
  }

  .fleet-table td {
    padding: var(--sp-2) var(--sp-3);
    border-bottom: 1px solid var(--border-0);
    white-space: nowrap;
  }

  .row {
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease);
  }
  .row:hover { background: var(--bg-2); }
  .row.selected {
    background: var(--bg-3);
    box-shadow: inset 2px 0 0 var(--accent);
  }
  .row.status-critical:not(.selected) { box-shadow: inset 2px 0 0 var(--status-critical-line); }
  .row.status-warning:not(.selected) { box-shadow: inset 2px 0 0 var(--status-warning-line); }
  .row.status-healthy:not(.selected) { box-shadow: inset 2px 0 0 var(--status-healthy-line); }

  .truncate {
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .status-cell {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-2);
  }
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
  .status-dot-critical { background: var(--status-critical-fg); box-shadow: 0 0 6px var(--status-critical-fg); }
  .status-dot-warning  { background: var(--status-warning-fg); }
  .status-dot-healthy  { background: var(--status-healthy-fg); }
  .status-dot-unknown  { background: var(--text-3); }

  .status-label {
    font-size: var(--fs-xs);
    letter-spacing: 0.1em;
    font-weight: 600;
  }
  .status-label-critical { color: var(--status-critical-fg); }
  .status-label-warning { color: var(--status-warning-fg); }
  .status-label-healthy { color: var(--status-healthy-fg); }
  .status-label-unknown { color: var(--text-3); }

  .score {
    display: inline-flex;
    align-items: baseline;
    gap: 2px;
    font-family: var(--font-display);
    font-weight: 600;
  }
  .score-num { font-size: var(--fs-md); }
  .score-max { font-size: var(--fs-xs); }
  .score-critical .score-num { color: var(--status-critical-fg); }
  .score-warning .score-num { color: var(--status-warning-fg); }
  .score-healthy .score-num { color: var(--status-healthy-fg); }

  .empty-row { padding: var(--sp-6); text-align: center; font-size: var(--fs-sm); }
`
