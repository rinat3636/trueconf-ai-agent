const API_BASE = '/api'

function getHeaders() {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

async function request(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: getHeaders(),
    ...options,
  })
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    return
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  // Auth
  login: (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  register: (data) => request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () => request('/auth/me'),
  getUsers: () => request('/auth/users'),

  // Chat
  ask: (data) => request('/chat/ask', { method: 'POST', body: JSON.stringify(data) }),
  submitFeedback: (data) => request('/chat/feedback', { method: 'POST', body: JSON.stringify(data) }),
  getChatHistory: (sessionId) => request(`/chat/history${sessionId ? `?session_id=${sessionId}` : ''}`),

  // Knowledge
  getDocuments: (category) => request(`/knowledge/documents${category ? `?category=${category}` : ''}`),
  uploadDocument: (file, category) => {
    const formData = new FormData()
    formData.append('file', file)
    if (category) formData.append('category', category)
    return fetch(`${API_BASE}/knowledge/documents/upload`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    }).then(r => r.json())
  },
  deleteDocument: (id) => request(`/knowledge/documents/${id}`, { method: 'DELETE' }),
  getKnowledgeItems: (category, approvedOnly) => {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (approvedOnly) params.set('approved_only', 'true')
    return request(`/knowledge/items?${params}`)
  },
  createKnowledgeItem: (data) => request('/knowledge/items', { method: 'POST', body: JSON.stringify(data) }),
  updateKnowledgeItem: (id, data) => request(`/knowledge/items/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteKnowledgeItem: (id) => request(`/knowledge/items/${id}`, { method: 'DELETE' }),

  // Rules
  getRules: () => request('/knowledge/rules'),
  createRule: (data) => request('/knowledge/rules', { method: 'POST', body: JSON.stringify(data) }),
  deleteRule: (id) => request(`/knowledge/rules/${id}`, { method: 'DELETE' }),

  // Corrections
  getCorrections: () => request('/knowledge/corrections'),
  createCorrection: (data) => request('/knowledge/corrections', { method: 'POST', body: JSON.stringify(data) }),

  // Moderation
  getModerationQueue: (status) => request(`/knowledge/moderation${status ? `?status=${status}` : ''}`),
  moderateItem: (id, action) => request(`/knowledge/moderation/${id}/action`, { method: 'POST', body: JSON.stringify({ action }) }),

  // Analytics
  getReports: () => request('/analytics/reports'),
  getReport: (id) => request(`/analytics/reports/${id}`),
  uploadReport: (file, reportType) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('report_type', reportType || 'sales')
    return fetch(`${API_BASE}/analytics/reports/upload`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    }).then(r => r.json())
  },
  getReportAnalytics: (id) => request(`/analytics/reports/${id}/analytics`),
  getReportManagers: (id) => request(`/analytics/reports/${id}/managers`),
  getReportClients: (id) => request(`/analytics/reports/${id}/clients`),
  getReportRecommendations: (id) => request(`/analytics/reports/${id}/recommendations`),
  askAnalytics: (data) => request('/analytics/ask', { method: 'POST', body: JSON.stringify(data) }),

  // Monitoring
  getStats: () => request('/monitoring/stats'),
}
