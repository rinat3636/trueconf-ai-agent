import React, { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '../services/api'

export default function MonitoringPage() {
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadStats() }, [])

  const loadStats = async () => {
    setLoading(true)
    try {
      const [s, h] = await Promise.all([
        api.getStats(),
        api.getHealth().catch(() => null),
      ])
      setStats(s)
      setHealth(h)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  if (loading) {
    return <div className="loading"><div className="spinner" /> Загрузка...</div>
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <h1>Мониторинг</h1>
          <p>Активность системы и использование</p>
        </div>
        <button className="btn btn-outline" onClick={loadStats}>
          <RefreshCw size={16} /> Обновить
        </button>
      </div>

      {health && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Здоровье сервисов</h3>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            {Object.entries(health.services || health).filter(([k]) => k !== 'status').map(([key, val]) => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{
                  width: 12, height: 12, borderRadius: '50%',
                  background: val === 'ok' || val === true ? '#16a34a' : '#dc2626',
                  display: 'inline-block'
                }} />
                <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>{key}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Документы</div>
            <div className="stat-value">{stats.total_documents}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Записи знаний</div>
            <div className="stat-value">{stats.total_knowledge_items}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Одобренные знания</div>
            <div className="stat-value">{stats.approved_knowledge_items}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Всего запросов</div>
            <div className="stat-value">{stats.total_queries}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Пользователи</div>
            <div className="stat-value">{stats.total_users}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Отчёты продаж</div>
            <div className="stat-value">{stats.total_reports}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">На модерации</div>
            <div className="stat-value" style={{ color: stats.pending_moderation > 0 ? '#ca8a04' : undefined }}>
              {stats.pending_moderation}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Позитивная обратная связь</div>
            <div className="stat-value">
              {stats.positive_feedback_pct != null ? `${stats.positive_feedback_pct}%` : 'N/A'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
