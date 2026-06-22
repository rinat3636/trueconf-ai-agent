import React, { useState, useEffect } from 'react'
import { Check, X, Clock, Eye } from 'lucide-react'
import { api } from '../services/api'

const TYPE_LABELS = {
  new_knowledge: 'Новое знание',
  bad_feedback: 'Плохой ответ',
  conflict: 'Конфликт',
  knowledge_update: 'Обновление',
  chat_insight: 'Из чата',
}

export default function ModerationPage() {
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState('pending')
  const [typeFilter, setTypeFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [detailModal, setDetailModal] = useState(null)

  useEffect(() => { loadItems() }, [filter, typeFilter])

  const loadItems = async () => {
    setLoading(true)
    try {
      const data = await api.getModerationQueue(filter, typeFilter || null)
      setItems(data)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const handleAction = async (id, action) => {
    try {
      await api.moderateItem(id, action)
      loadItems()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Модерация</h1>
        <p>Проверка и одобрение новых знаний</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {['pending', 'approved', 'rejected'].map(f => (
              <button key={f} className={`btn ${filter === f ? 'btn-primary' : 'btn-outline'} btn-sm`}
                onClick={() => setFilter(f)}>
                {{ pending: 'Ожидают', approved: 'Одобренные', rejected: 'Отклонённые' }[f]}
              </button>
            ))}
            <span style={{ borderLeft: '1px solid #d1d5db', margin: '0 0.25rem' }} />
            <select className="form-control" style={{ width: '160px', padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
              value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
              <option value="">Все типы</option>
              {Object.entries(TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>{items.length} элементов</span>
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Загрузка...</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <Clock size={48} color="#d1d5db" />
            <p>Нет элементов в очереди «{{ pending: 'ожидающие', approved: 'одобренные', rejected: 'отклонённые' }[filter]}»</p>
          </div>
        ) : (
          items.map(item => (
            <div key={item.id} style={{
              padding: '1rem',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'start',
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <span className={`badge badge-${
                    item.item_type === 'new_knowledge' ? 'info' :
                    item.item_type === 'bad_feedback' ? 'danger' :
                    item.item_type === 'conflict' ? 'warning' : 'info'
                  }`}>
                    {TYPE_LABELS[item.item_type] || item.item_type}
                  </span>
                  <strong>{item.title || `#${item.id}`}</strong>
                </div>
                <p style={{ fontSize: '0.85rem', color: '#4b5563', whiteSpace: 'pre-wrap' }}>
                  {(item.content || '').substring(0, 300)}{(item.content || '').length > 300 ? '...' : ''}
                </p>
                {item.payload && (
                  <button className="btn btn-outline btn-sm" style={{ marginTop: '0.25rem' }}
                    onClick={() => setDetailModal(item.payload)}>
                    <Eye size={12} /> Подробнее
                  </button>
                )}
              </div>
              {filter === 'pending' && (
                <div style={{ display: 'flex', gap: '0.5rem', marginLeft: '1rem' }}>
                  <button className="btn btn-success btn-sm" onClick={() => handleAction(item.id, 'approve')}>
                    <Check size={14} /> Одобрить
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleAction(item.id, 'reject')}>
                    <X size={14} /> Отклонить
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {detailModal && (
        <div className="modal-overlay" onClick={() => setDetailModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <h3 className="modal-title">Детали</h3>
            <pre style={{
              background: '#f1f5f9', padding: '1rem', borderRadius: '0.5rem',
              fontSize: '0.8rem', overflow: 'auto', maxHeight: '60vh',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {JSON.stringify(detailModal, null, 2)}
            </pre>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setDetailModal(null)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
