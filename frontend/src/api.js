export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function endpoint(path) {
  return `${API_BASE}${path}`
}

export async function apiGet(path) {
  const response = await fetch(endpoint(path))
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`)
  }
  return response.json()
}

export async function apiPost(path, body = undefined) {
  const response = await fetch(endpoint(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`POST ${path} failed: ${response.status} ${detail}`)
  }
  return response.json()
}

export async function apiPut(path, body) {
  const response = await fetch(endpoint(path), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`PUT ${path} failed: ${response.status} ${detail}`)
  }
  return response.json()
}

export function wsUrl(path) {
  const base = API_BASE.replace(/^http/, 'ws')
  return `${base}${path}`
}

export function assetUrl(relativePath) {
  const trimmed = relativePath.startsWith('/') ? relativePath.slice(1) : relativePath
  return `${API_BASE}/assets/${trimmed}`
}
