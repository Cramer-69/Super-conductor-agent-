// Thin client for the Semantic Wall backend (semantic_wall/api/main.py).
// Mirrors the same role as ios/ConductorApp's ConductorClient.swift — a
// minimal networking layer other clients can copy the shape of.

const BASE_URL = import.meta.env.VITE_SEMANTIC_WALL_URL || 'http://localhost:8090'

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request to ${path} failed (${response.status})`)
  }
  return response.json()
}

export function health() {
  return request('/health')
}

export function chat({ userId, sessionId, query, agentId = 'strategist' }) {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, session_id: sessionId, query, agent_id: agentId }),
  })
}

export function checkinStatus(sessionId) {
  return request(`/api/checkin/status?session_id=${encodeURIComponent(sessionId)}`)
}

export function submitCheckin({ userId, sessionId, agentId = 'strategist', answers }) {
  return request('/api/checkin', {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      session_id: sessionId,
      agent_id: agentId,
      completion_confirmation: answers.completionConfirmation,
      quality_rating: answers.qualityRating,
      improvement_note: answers.improvementNote,
      used_in_real_work: answers.usedInRealWork,
      willingness_to_pay: answers.willingnessToPay,
      price_point_cents: answers.pricePointCents ?? null,
    }),
  })
}
