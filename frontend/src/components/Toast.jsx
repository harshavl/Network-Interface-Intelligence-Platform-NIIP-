import { AlertCircle, X } from 'lucide-react'

export default function Toast({ error, onDismiss }) {
  if (!error) return null
  return (
    <div className="toast fade-in">
      <AlertCircle size={14} />
      <div className="toast-body">
        <div className="toast-title">{error.code || 'ERROR'}</div>
        <div className="toast-message">{error.message}</div>
      </div>
      <button className="toast-close" onClick={onDismiss} aria-label="Dismiss">
        <X size={14} />
      </button>

      <style>{`
        .toast {
          position: fixed;
          bottom: var(--sp-4);
          right: var(--sp-4);
          z-index: 100;
          display: flex;
          align-items: flex-start;
          gap: var(--sp-3);
          padding: var(--sp-3) var(--sp-4);
          background: var(--bg-2);
          border: 1px solid var(--status-critical-line);
          border-left: 3px solid var(--status-critical-fg);
          color: var(--status-critical-fg);
          max-width: 420px;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
        }
        .toast-body { flex: 1; min-width: 0; }
        .toast-title {
          font-size: var(--fs-xs);
          font-weight: 700;
          letter-spacing: 0.15em;
          color: var(--status-critical-fg);
          margin-bottom: 2px;
        }
        .toast-message {
          font-size: var(--fs-sm);
          color: var(--text-0);
          line-height: var(--lh-normal);
          word-break: break-word;
        }
        .toast-close {
          color: var(--text-2);
          padding: 2px;
          flex-shrink: 0;
        }
        .toast-close:hover { color: var(--text-0); }
      `}</style>
    </div>
  )
}
