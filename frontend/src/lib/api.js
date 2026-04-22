
/**
 * API client — thin wrapper over fetch() against the Flask backend.
 *
 * All endpoints return JSON. Errors are surfaced as thrown Error with the
 * server's error code and message preserved.
 */

const BASE = '/api/v1'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)

  // Non-2xx: try to parse the structured error payload, else fall back to text
  if (!res.ok) {
    let body
    try {
      body = await res.json()
    } catch {
      body = { error: 'HTTP_ERROR', message: res.statusText }
    }
    const err = new Error(body.message || `HTTP ${res.status}`)
    err.code = body.error
    err.status = res.status
    err.details = body.details
    throw err
  }

  return res.json()
}

export async function getHealth() {
  return request('/health')
}

export async function analyzeUpload(file) {
  const fd = new FormData()
  fd.append('file', file)
  return request('/analysis/upload', {
    method: 'POST',
    body: fd,
  })
}

export async function analyzeJson(payload) {
  return request('/analysis/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function getSummary(file) {
  const fd = new FormData()
  fd.append('file', file)
  return request('/analysis/summary', {
    method: 'POST',
    body: fd,
  })
}
