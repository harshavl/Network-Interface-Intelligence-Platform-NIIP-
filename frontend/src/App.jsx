import { useCallback, useState } from 'react'
import StatusBar from './components/StatusBar'
import SummaryTiles from './components/SummaryTiles'
import UploadPanel from './components/UploadPanel'
import FleetGrid from './components/FleetGrid'
import InterfaceDetail from './components/InterfaceDetail'
import HealthChart from './components/HealthChart'
import Toast from './components/Toast'
import { analyzeUpload } from './lib/api'

export default function App() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [fileName, setFileName] = useState(null)
  const [selected, setSelected] = useState(null)

  const handleAnalyze = useCallback(async (file) => {
    setLoading(true)
    setError(null)
    setFileName(file.name)
    setSelected(null)
    try {
      const result = await analyzeUpload(file)
      setReport(result)
    } catch (err) {
      setError({
        code: err.code || 'UPLOAD_ERROR',
        message: err.message || 'Failed to analyze file.',
      })
      setReport(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleClear = useCallback(() => {
    setReport(null)
    setFileName(null)
    setSelected(null)
    setError(null)
  }, [])

  const selectedId = selected
    ? `${selected.device}__${selected.interface}`
    : null

  return (
    <div className="app">
      <StatusBar report={report} />

      <main className="main">
        <div className="col-left">
          <UploadPanel
            onAnalyze={handleAnalyze}
            loading={loading}
            fileName={fileName}
            onClear={handleClear}
          />
          <SummaryTiles summary={report?.summary} loading={loading} />
          <HealthChart interfaces={report?.interfaces} />
          <div className="fleet-wrap">
            <FleetGrid
              interfaces={report?.interfaces}
              selectedId={selectedId}
              onSelect={(iface) => setSelected(iface)}
            />
          </div>
        </div>

        <div className="col-right">
          <InterfaceDetail
            iface={selected}
            onClose={() => setSelected(null)}
          />
        </div>
      </main>

      <Toast error={error} onDismiss={() => setError(null)} />

      <style>{`
        .app {
          position: relative;
          z-index: 1;
          height: 100vh;
          width: 100vw;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .main {
          flex: 1;
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(380px, 480px);
          gap: var(--sp-3);
          padding: var(--sp-3);
          min-height: 0;
          overflow: hidden;
        }

        .col-left {
          display: flex;
          flex-direction: column;
          gap: var(--sp-3);
          min-width: 0;
          min-height: 0;
        }

        .col-right {
          display: flex;
          flex-direction: column;
          min-height: 0;
        }

        .fleet-wrap {
          flex: 1;
          min-height: 0;
          display: flex;
        }

        @media (max-width: 1100px) {
          .main {
            grid-template-columns: 1fr;
          }
          .col-right {
            max-height: 360px;
          }
        }
      `}</style>
    </div>
  )
}
