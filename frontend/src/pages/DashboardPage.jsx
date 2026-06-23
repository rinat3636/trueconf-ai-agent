import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Brain, MessageSquare, Users, BarChart3,
  Shield, AlertTriangle, TrendingUp, RefreshCw
} from 'lucide-react'
import { api } from '../services/api'

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
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

  const cards = stats ? [
    { label: 'Документы', value: stats.total_documents, icon: FileText, color: '#2563eb' },
    { label: 'Знания', value: stats.total_knowledge_items, icon: Brain, color: '#7c3aed' },
    { label: 'Одобренные', value: stats.approved_knowledge_items, icon: TrendingUp, color: '#16a34a' },
    { label: 'Запросы', value: stats.total_queries, icon: MessageSquare, color: '#0891b2' },
    { label: 'Пользователи', value: stats.total_users, icon: Users, color: '#4f46e5' },
    { label: 'Отчёты продаж', value: stats.total_reports, icon: BarChart3, color: '#ea580c' },
    { label: 'На модерации', value: stats.pending_moderation, icon: Shield, color: stats.pending_moderation > 0 ? '#ca8a04' : '#6b7280', onClick: () => navigate('/moderation') },
    { label: 'Обратная связь +', value: stats.positive_feedback_pct != null ? `${stats.positive_feedback_pct}%` : 'N/A', icon: TrendingUp, color: '#16a34a' },
  ] : []

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Панель управления</h1>
          <p>Обзор системы ИИ-агента</p>
        </div>
        <button className="btn btn-outline" onClick={loadData}>
          <RefreshCw size={16} /> Обновить
        </button>
      </div>

      <div className="stats-grid">
        {cards.map((c, i) => (
          <div key={i} className="stat-card" onClick={c.onClick} style={c.onClick ? { cursor: 'pointer' } : {}}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div className="stat-label">{c.label}</div>
                <div className="stat-value" style={{ color: c.color }}>{c.value}</div>
              </div>
              <c.icon size={32} color={c.color} style={{ opacity: 0.3 }} />
            </div>
          </div>
        ))}
      </div>

      {health && (
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Состояние сервисов</h3>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {Object.entries(health.services || health).filter(([k]) => k !== 'status').map(([key, val]) => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{
                  width: 10, height: 10, borderRadius: '50%',
                  background: val === 'ok' || val === true ? '#16a34a' : '#dc2626',
                  display: 'inline-block'
                }} />
                <span style={{ fontSize: '0.85rem' }}>{key}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid-2">
        <div className="card" onClick={() => navigate('/moderation')} style={{ cursor: 'pointer' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Shield size={24} color="#ca8a04" />
            <div>
              <div style={{ fontWeight: 600 }}>Очередь модерации</div>
              <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                {stats?.pending_moderation || 0} элементов ожидают проверки
              </div>
            </div>
          </div>
        </div>
        <div className="card" onClick={() => navigate('/sales')} style={{ cursor: 'pointer' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <BarChart3 size={24} color="#ea580c" />
            <div>
              <div style={{ fontWeight: 600 }}>Аналитика продаж</div>
              <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                {stats?.total_reports || 0} загруженных отчётов
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
