import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

/**
 * Small score-distribution histogram. Buckets interfaces into 10-point
 * bands and colors by the worst status that falls in each band.
 */
export default function HealthChart({ interfaces }) {
  const data = useMemo(() => {
    const buckets = []
    for (let i = 0; i < 10; i++) {
      buckets.push({
        range: `${i * 10}-${i * 10 + 9}`,
        count: 0,
        worst: 'healthy',
        lo: i * 10,
        hi: i * 10 + 9,
      })
    }
    if (!interfaces) return buckets

    const order = { critical: 0, warning: 1, healthy: 2 }
    interfaces.forEach((iface) => {
      const idx = Math.min(9, Math.floor(iface.health_score / 10))
      buckets[idx].count += 1
      if (order[iface.status] < order[buckets[idx].worst]) {
        buckets[idx].worst = iface.status
      }
    })
    return buckets
  }, [interfaces])

  const max = Math.max(...data.map((d) => d.count), 1)

  return (
    <section className="chart-panel">
      <header className="chart-head">
        <span className="text-2 uppercase" style={{ fontSize: 'var(--fs-xs)', letterSpacing: '0.15em' }}>
          SCORE DISTRIBUTION
        </span>
        <span className="text-3 tabular" style={{ fontSize: 'var(--fs-xs)' }}>
          n={interfaces?.length ?? 0}
        </span>
      </header>

      <div className="chart-body">
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
            <XAxis
              dataKey="range"
              tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
              axisLine={{ stroke: 'var(--border-1)' }}
              tickLine={false}
              interval={0}
            />
            <YAxis
              tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
              axisLine={false}
              tickLine={false}
              width={28}
              allowDecimals={false}
              domain={[0, max]}
            />
            <Tooltip
              cursor={{ fill: 'var(--bg-3)' }}
              contentStyle={{
                background: 'var(--bg-2)',
                border: '1px solid var(--border-2)',
                borderRadius: 0,
                fontSize: 12,
                fontFamily: 'var(--font-mono)',
                padding: '6px 10px',
              }}
              labelStyle={{ color: 'var(--text-2)', fontSize: 10, letterSpacing: '0.1em' }}
              itemStyle={{ color: 'var(--text-0)' }}
              formatter={(value) => [value, 'count']}
              labelFormatter={(label) => `SCORE ${label}`}
            />
            <Bar dataKey="count" radius={0}>
              {data.map((entry, i) => (
                <Cell key={i} fill={`var(--status-${entry.worst}-fg)`} opacity={entry.count > 0 ? 0.85 : 0.2} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <style>{`
        .chart-panel {
          background: var(--bg-1);
          border: 1px solid var(--border-0);
          padding: var(--sp-3) var(--sp-4);
          min-height: 170px;
          display: flex;
          flex-direction: column;
        }
        .chart-head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--sp-2);
        }
        .chart-body {
          flex: 1;
          min-height: 0;
        }
      `}</style>
    </section>
  )
}
