import React, { useState, useEffect } from 'react'
import { RefreshCw, Eye } from 'lucide-react'
import { api } from '../services/api'

export default function AuditPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [limit, setLimit] = useState(100)
  const [actionFilter, setActionFilter] = useState('')
  const [detailModal, setDetailModal] = useState(null)

  useEffect(() => { loadLogs() }, [limit, actionFilter])

  const loadLogs = async () => {
    setLoading(true)
    try {
      const data = await api.getAuditLog(limit, actionFilter || null)
      setLogs(data)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const actionColor = (action) => {
    if (action?.includes('delete') || action?.includes('reject')) return 'danger'
    if (action?.includes('create') || action?.includes('approve') || action?.includes('upload')) return 'success'
    if (action?.includes('update') || action?.includes('login')) return 'info'
    return 'warning'
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Журнал аудита</h1>
          <p>История всех действий в системе</p>
        </div>
        <button className="btn btn-outline" onClick={loadLogs}>
          <RefreshCw size={16} /> Обновить
        </button>
      </div>

      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <input className="form-control" style={{ width: '200px' }} value={actionFilter}
              onChange={e => setActionFilter(e.target.value)} placeholder="Фильтр по действию..." />
            <select className="form-control" style={{ width: '120px' }} value={limit}
              onChange={e => setLimit(parseInt(e.target.value))}>
              <option value="50">50 записей</option>
              <option value="100">100 записей</option>
              <option value="200">200 записей</option>
              <option value="500">500 записей</option>
            </select>
          </div>
          <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>{logs.length} записей</span>
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Загрузка...</div>
        ) : logs.length === 0 ? (
          <div className="empty-state"><p>Нет записей аудита</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Пользователь</th>
                  <th>Действие</th>
                  <th>Сущность</th>
                  <th>ID</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <tr key={log.id || i}>
                    <td style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                      {new Date(log.created_at).toLocaleString('ru-RU')}
                    </td>
                    <td>{log.user_id || log.username || '-'}</td>
                    <td>
                      <span className={`badge badge-${actionColor(log.action)}`}>
                        {log.action}
                      </span>
                    </td>
                    <td>{log.entity_type || '-'}</td>
                    <td>{log.entity_id || '-'}</td>
                    <td>
                      {(log.details || log.changes) && (
                        <button className="btn btn-outline btn-sm"
                          onClick={() => setDetailModal(log.details || log.changes)}>
                          <Eye size={12} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {detailModal && (
        <div className="modal-overlay" onClick={() => setDetailModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <h3 className="modal-title">Детали действия</h3>
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
