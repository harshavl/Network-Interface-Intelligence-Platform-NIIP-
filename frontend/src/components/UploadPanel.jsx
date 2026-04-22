import { useCallback, useRef, useState } from 'react'
import { Upload, FileText, Play, X } from 'lucide-react'
import { sampleFile } from '../lib/sampleData'

export default function UploadPanel({ onAnalyze, loading, fileName, onClear }) {
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef(null)

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      e.stopPropagation()
      setDragActive(false)
      const file = e.dataTransfer?.files?.[0]
      if (file) onAnalyze(file)
    },
    [onAnalyze],
  )

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (file) onAnalyze(file)
  }

  return (
    <section
      className={`upload-panel ${dragActive ? 'drag-active' : ''}`}
      onDragEnter={(e) => { e.preventDefault(); setDragActive(true) }}
      onDragLeave={(e) => { e.preventDefault(); setDragActive(false) }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      <div className="upload-head">
        <span className="upload-tag text-2 uppercase">INPUT</span>
        {fileName && (
          <div className="file-badge">
            <FileText size={12} />
            <span>{fileName}</span>
            <button className="clear-btn" onClick={onClear} aria-label="Clear">
              <X size={12} />
            </button>
          </div>
        )}
      </div>

      <div className="upload-body">
        <div className="upload-hint">
          <Upload size={16} className="text-2" />
          <div>
            <div className="text-0">
              {dragActive ? 'Release to upload' : 'Drop LogicMonitor CSV here'}
            </div>
            <div className="text-2" style={{ fontSize: 'var(--fs-xs)' }}>
              or click to browse · max 50 MB
            </div>
          </div>
        </div>

        <div className="upload-actions">
          <button
            className="btn btn-ghost"
            onClick={() => inputRef.current?.click()}
            disabled={loading}
          >
            <FileText size={13} />
            <span>BROWSE</span>
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onAnalyze(sampleFile())}
            disabled={loading}
          >
            <Play size={13} />
            <span>{loading ? 'ANALYZING…' : 'LOAD SAMPLE'}</span>
          </button>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        style={{ display: 'none' }}
        onChange={handleFileSelect}
      />

      <style>{`
        .upload-panel {
          background: var(--bg-1);
          border: 1px solid var(--border-0);
          border-left: 2px solid var(--accent);
          padding: var(--sp-3) var(--sp-4);
          transition: border-color var(--dur-fast) var(--ease);
        }
        .upload-panel.drag-active {
          border-color: var(--accent);
          background: var(--bg-2);
          box-shadow: inset 0 0 0 1px var(--accent-glow);
        }

        .upload-head {
          display: flex;
          align-items: center;
          gap: var(--sp-3);
          margin-bottom: var(--sp-2);
        }
        .upload-tag {
          font-size: var(--fs-xs);
          letter-spacing: 0.15em;
        }
        .file-badge {
          display: inline-flex;
          align-items: center;
          gap: var(--sp-2);
          padding: 2px var(--sp-2);
          background: var(--bg-3);
          border: 1px solid var(--border-1);
          font-size: var(--fs-xs);
          color: var(--text-1);
        }
        .clear-btn {
          color: var(--text-2);
          padding: 2px;
          display: flex;
          align-items: center;
        }
        .clear-btn:hover { color: var(--status-critical-fg); }

        .upload-body {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: var(--sp-4);
        }

        .upload-hint {
          display: flex;
          align-items: center;
          gap: var(--sp-3);
          color: var(--text-1);
        }

        .upload-actions {
          display: flex;
          gap: var(--sp-2);
        }

        .btn {
          display: inline-flex;
          align-items: center;
          gap: var(--sp-2);
          padding: 6px var(--sp-3);
          font-family: var(--font-mono);
          font-size: var(--fs-sm);
          font-weight: 600;
          letter-spacing: 0.08em;
          border: 1px solid var(--border-2);
          transition: all var(--dur-fast) var(--ease);
          white-space: nowrap;
        }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-ghost { color: var(--text-1); background: transparent; }
        .btn-ghost:hover:not(:disabled) {
          color: var(--text-0);
          border-color: var(--text-1);
          background: var(--bg-3);
        }
        .btn-primary {
          color: var(--bg-0);
          background: var(--accent);
          border-color: var(--accent);
        }
        .btn-primary:hover:not(:disabled) {
          background: #a8e3ff;
          border-color: #a8e3ff;
          box-shadow: 0 0 12px var(--accent-glow);
        }
      `}</style>
    </section>
  )
}
