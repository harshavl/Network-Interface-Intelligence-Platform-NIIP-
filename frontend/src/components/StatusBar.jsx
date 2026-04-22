import { useEffect, useState } from 'react'
import { getHealth } from '../lib/api'

export default function StatusBar({ report }) {
  const [time, setTime] = useState(new Date())
  const [apiStatus, setApiStatus] = useState('connecting')

  useEffect(() => {
    const clock = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(clock)
  }, [])

  useEffect(() => {
    let alive = true
    const check = async () => {
      try {
        await getHealth()
        if (alive) setApiStatus('online')
      } catch {
        if (alive) setApiStatus('offline')
      }
    }
    check()
    const iv = setInterval(check, 15_000)
    return () => {
      alive = false
      clearInterval(iv)
    }
  }, [])

  const timeStr = time.toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
  const count = report?.summary?.total_interfaces ?? 0

  return (
    <header className="status-bar">
      <div className="status-left">
        <div className="brand">
          <span className="brand-bracket">[</span>
          <span className="brand-name">NIIP</span>
          <span className="brand-bracket">]</span>
          <span className="brand-sub">NETWORK INTERFACE INTELLIGENCE</span>
        </div>
      </div>
      <div className="status-center">
        <Indicator label="API" value={apiStatus} kind={apiStatus} />
        <Indicator label="INTERFACES" value={count} kind="neutral" />
        <Indicator
          label="MODE"
          value={report ? 'ANALYSIS' : 'STANDBY'}
          kind="neutral"
        />
      </div>
      <div className="status-right">
        <span className="text-2 uppercase">UTC</span>
        <span className="tabular text-0">{timeStr}</span>
      </div>

      <style>{`
        .status-bar {
          display: grid;
          grid-template-columns: 1fr auto 1fr;
          align-items: center;
          height: 44px;
          padding: 0 var(--sp-4);
          border-bottom: 1px solid var(--border-1);
          background: var(--bg-1);
          position: relative;
          z-index: 10;
          flex: 0 0 auto;
        }

        .status-left { display: flex; align-items: center; }
        .status-center {
          display: flex;
          align-items: center;
          gap: var(--sp-3);
        }
        .status-right {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: var(--sp-3);
          font-size: var(--fs-sm);
        }

        .brand {
          display: flex;
          align-items: center;
          gap: var(--sp-2);
          font-family: var(--font-display);
          font-weight: 700;
          letter-spacing: 0.02em;
        }
        .brand-bracket {
          color: var(--accent);
          font-weight: 500;
          font-size: var(--fs-xl);
        }
        .brand-name {
          font-size: var(--fs-lg);
          color: var(--text-0);
          letter-spacing: 0.1em;
        }
        .brand-sub {
          font-family: var(--font-mono);
          font-weight: 400;
          font-size: var(--fs-xs);
          color: var(--text-2);
          letter-spacing: 0.15em;
          margin-left: var(--sp-2);
        }
      `}</style>
    </header>
  )
}

function Indicator({ label, value, kind = 'neutral' }) {
  const dotClass = `dot ${kind}`
  const valueDisplay = typeof value === 'string' ? value.toUpperCase() : value
  return (
    <div className="indicator">
      <span className={dotClass} aria-hidden />
      <span className="ind-label text-2 uppercase">{label}</span>
      <span className="ind-value text-0 tabular">{valueDisplay}</span>

      <style>{`
        .indicator {
          display: flex;
          align-items: center;
          gap: var(--sp-2);
          font-size: var(--fs-xs);
          letter-spacing: 0.1em;
        }
        .ind-value { font-size: var(--fs-sm); font-weight: 600; }

        .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--text-3);
        }
        .dot.online { background: var(--status-healthy-fg); box-shadow: 0 0 6px var(--status-healthy-fg); animation: pulse 2s ease-in-out infinite; }
        .dot.offline { background: var(--status-critical-fg); box-shadow: 0 0 6px var(--status-critical-fg); }
        .dot.connecting { background: var(--status-warning-fg); animation: pulse 1s ease-in-out infinite; }
        .dot.neutral { background: var(--text-3); }
      `}</style>
    </div>
  )
}
