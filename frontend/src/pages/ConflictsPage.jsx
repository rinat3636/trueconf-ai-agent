import React, { useState, useEffect } from 'react'
import { AlertTriangle, Check } from 'lucide-react'
import { api } from '../services/api'

const RESOLUTION_OPTIONS = [
  { value: 'replace_old', label: 'Заменить старое' },
  { value: 'keep_old', label: 'Оставить старое' },
  { value: 'merge', label: 'Объединить' },
]

const CONFLICT_TYPE_LABELS = {
  contradiction: 'Противоречие',
  duplicate: 'Дубликат',
  partial_overlap: 'Частичное пересечение',
}

export default function ConflictsPage() {
  const [conflicts, setConflicts] = useState([])
  const [filter, setFilter] = useState('pending')
  const [loading, setLoading] = useState(true)
  const [resolveModal, setResolveModal] = useState(null)
  const [resolution, setResolution] = useState('replace_old')
  const [comment, setComment] = useState('')

  useEffect(() => { loadConflicts() }, [filter])

  const loadConflicts = async () => {
    setLoading(true)
    try {
      const data = await api.getConflicts(filter)
      setConflicts(data)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const handleResolve = async () => {
    try {
      await api.resolveConflict(resolveModal.id, { resolution, comment })
      setResolveModal(null)
      setResolution('replace_old')
      setComment('')
      loadConflicts()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Конфликты знаний</h1>
        <p>Разрешение противоречий между документами</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {['pending', 'resolved'].map(f => (
              <button key={f} className={`btn ${filter === f ? 'btn-primary' : 'btn-outline'} btn-sm`}
                onClick={() => setFilter(f)}>
                {{ pending: 'Нерешённые', resolved: 'Решённые' }[f]}
              </button>
            ))}
          </div>
          <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>{conflicts.length} конфликтов</span>
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Загрузка...</div>
        ) : conflicts.length === 0 ? (
          <div className="empty-state">
            <AlertTriangle size={48} color="#d1d5db" />
            <p>Нет конфликтов</p>
          </div>
        ) : (
          conflicts.map(c => (
            <div key={c.id} className="conflict-item">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', gap: '0.375rem', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                  <AlertTriangle size={16} color="#ca8a04" />
                  <strong>Конфликт #{c.id}</strong>
                  {c.conflict_type && (
                    <span className="badge badge-warning">{CONFLICT_TYPE_LABELS[c.conflict_type] || c.conflict_type}</span>
                  )}
                  {c.similarity_score != null && (
                    <span className="badge badge-warning">Сходство: {(c.similarity_score * 100).toFixed(0)}%</span>
                  )}
                  {filter === 'pending' && (
                    <button className="btn btn-primary btn-sm" style={{ marginLeft: 'auto' }}
                      onClick={() => setResolveModal(c)}>
                      <Check size={14} /> Решить
                    </button>
                  )}
                  {c.resolution && (
                    <span className="badge badge-success" style={{ marginLeft: 'auto' }}>
                      {RESOLUTION_OPTIONS.find(o => o.value === c.resolution)?.label || c.resolution}
                    </span>
                  )}
                </div>

                <div className="grid-2" style={{ gap: '0.75rem' }}>
                  <div style={{ padding: '0.625rem', background: '#fef2f2', borderRadius: '0.5rem' }}>
                    <div style={{ fontSize: '0.7rem', color: '#991b1b', marginBottom: '0.25rem', fontWeight: 600 }}>
                      Существующее знание{c.existing_title ? `: ${c.existing_title}` : ''}
                    </div>
                    <p style={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{c.existing_content_preview || '—'}</p>
                  </div>
                  <div style={{ padding: '0.625rem', background: '#f0fdf4', borderRadius: '0.5rem' }}>
                    <div style={{ fontSize: '0.7rem', color: '#166534', marginBottom: '0.25rem', fontWeight: 600 }}>
                      Новое знание{c.new_title ? `: ${c.new_title}` : ''}
                    </div>
                    <p style={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{c.new_content_preview || '—'}</p>
                  </div>
                </div>

                {c.llm_analysis && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#4b5563', fontStyle: 'italic', wordBreak: 'break-word' }}>
                    Анализ ИИ: {c.llm_analysis}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {resolveModal && (
        <div className="modal-overlay" onClick={() => setResolveModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Разрешить конфликт #{resolveModal.id}</h3>
            <div className="form-group">
              <label>Решение</label>
              <select className="form-control" value={resolution} onChange={e => setResolution(e.target.value)}>
                {RESOLUTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Комментарий</label>
              <textarea className="form-control" value={comment} onChange={e => setComment(e.target.value)}
                placeholder="Почему выбрано такое решение..." />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setResolveModal(null)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleResolve}>Применить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
