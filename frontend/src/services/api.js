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
    window.location.href = '/'
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
  register: (data) => request('/auth/users', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () => request('/auth/me'),
  getUsers: () => request('/auth/users'),

  // Chat
  ask: (data) => request('/chat/ask', { method: 'POST', body: JSON.stringify(data) }),
  submitFeedback: (data) => request('/chat/feedback', { method: 'POST', body: JSON.stringify(data) }),
  getChatSessions: (limit) => request(`/chat/sessions${limit ? `?limit=${limit}` : ''}`),
  getChatMessages: (sessionId) => request(`/chat/messages/${sessionId}`),
  getChatHistory: (limit) => request(`/chat/history${limit ? `?limit=${limit}` : ''}`),

  // Knowledge - Documents
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

  // Knowledge - Items
  getKnowledgeItems: (category, status) => {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (status) params.set('status', status)
    return request(`/knowledge/items?${params}`)
  },
  createKnowledgeItem: (data) => request('/knowledge/items', { method: 'POST', body: JSON.stringify(data) }),
  updateKnowledgeItem: (id, data) => request(`/knowledge/items/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteKnowledgeItem: (id) => request(`/knowledge/items/${id}`, { method: 'DELETE' }),
  searchKnowledge: (query, category) => {
    const params = new URLSearchParams({ query })
    if (category) params.set('category', category)
    return request(`/knowledge/search?${params}`)
  },

  // Knowledge - Rules
  getRules: () => request('/knowledge/rules'),
  createRule: (data) => request('/knowledge/rules', { method: 'POST', body: JSON.stringify(data) }),
  updateRule: (id, data) => request(`/knowledge/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteRule: (id) => request(`/knowledge/rules/${id}`, { method: 'DELETE' }),

  // Knowledge - Corrections
  getCorrections: () => request('/knowledge/corrections'),
  createCorrection: (data) => request('/knowledge/corrections', { method: 'POST', body: JSON.stringify(data) }),

  // Knowledge - Moderation
  getModerationQueue: (status, itemType) => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (itemType) params.set('item_type', itemType)
    return request(`/knowledge/moderation?${params}`)
  },
  moderateItem: (id, action, comment) => request(`/knowledge/moderation/${id}/action`, {
    method: 'POST',
    body: JSON.stringify({ action, comment }),
  }),

  // Knowledge - Conflicts
  getConflicts: (status) => request(`/knowledge/conflicts${status ? `?status=${status}` : ''}`),
  resolveConflict: (id, data) => request(`/knowledge/conflicts/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Knowledge - Reindex
  reindex: () => request('/knowledge/reindex', { method: 'POST' }),

  // Analytics
  getReports: () => request('/analytics/reports'),
  getReport: (id) => request(`/analytics/reports/${id}`),
  deleteReport: (id) => request(`/analytics/reports/${id}`, { method: 'DELETE' }),
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
  getReportProducts: (id) => request(`/analytics/reports/${id}/products`),
  getReportRecommendations: (id) => request(`/analytics/reports/${id}/recommendations`),
  getFullAnalysis: (id) => request(`/analytics/reports/${id}/full-analysis`),
  askAnalytics: (data) => request('/analytics/ask', { method: 'POST', body: JSON.stringify(data) }),
  compareReports: (currentId, previousId) => request(`/analytics/reports/compare/${currentId}/${previousId}`),
  reindexReport: (id) => request(`/analytics/reports/${id}/reindex`, { method: 'POST' }),

  // Settings
  getBotSettings: () => request('/settings/bot'),
  updateBotSettings: (data) => request('/settings/bot', { method: 'PUT', body: JSON.stringify(data) }),

  // Users
  updateUser: (id, data) => request(`/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Monitoring
  getStats: () => request('/monitoring/stats'),
  getHealth: () => request('/monitoring/health'),
  getAuditLog: (limit, action) => {
    const params = new URLSearchParams()
    if (limit) params.set('limit', limit)
    if (action) params.set('action', action)
    return request(`/monitoring/audit?${params}`)
  },
}
