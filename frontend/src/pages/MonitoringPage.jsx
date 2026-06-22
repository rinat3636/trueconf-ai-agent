import React, { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '../services/api'

export default function MonitoringPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadStats() }, [])

  const loadStats = async () => {
    setLoading(true)
    try {
      const data = await api.getStats()
      setStats(data)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  if (loading) {
    return <div className="loading"><div className="spinner" /> Loading stats...</div>
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>System Monitoring</h1>
          <p>Overview of system activity and usage</p>
        </div>
        <button className="btn btn-outline" onClick={loadStats}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Documents</div>
            <div className="stat-value">{stats.total_documents}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Knowledge Items</div>
            <div className="stat-value">{stats.total_knowledge_items}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Approved Knowledge</div>
            <div className="stat-value">{stats.approved_knowledge_items}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Queries</div>
            <div className="stat-value">{stats.total_queries}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Users</div>
            <div className="stat-value">{stats.total_users}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Sales Reports</div>
            <div className="stat-value">{stats.total_reports}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Pending Moderation</div>
            <div className="stat-value" style={{ color: stats.pending_moderation > 0 ? '#ca8a04' : undefined }}>
              {stats.pending_moderation}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Positive Feedback</div>
            <div className="stat-value">
              {stats.positive_feedback_pct != null ? `${stats.positive_feedback_pct}%` : 'N/A'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
