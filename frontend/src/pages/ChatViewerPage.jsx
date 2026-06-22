import React, { useState, useEffect } from 'react'
import { MessageSquare, ChevronRight, Clock, Eye } from 'lucide-react'
import { api } from '../services/api'

export default function ChatViewerPage() {
  const [sessions, setSessions] = useState([])
  const [selectedSession, setSelectedSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [traceModal, setTraceModal] = useState(null)

  useEffect(() => { loadSessions() }, [])

  const loadSessions = async () => {
    setLoading(true)
    try {
      const data = await api.getChatSessions(100)
      setSessions(data)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const selectSession = async (session) => {
    setSelectedSession(session)
    try {
      const data = await api.getChatMessages(session.id)
      setMessages(data)
    } catch (err) { console.error(err) }
  }

  const channelLabel = (ch) => {
    const map = { trueconf: 'TrueConf', web: 'Веб', api: 'API' }
    return map[ch] || ch
  }

  return (
    <div>
      <div className="page-header">
        <h1>История чатов</h1>
        <p>Просмотр всех сессий и трассировка ответов</p>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem' }}>
        <div style={{ width: '320px', flexShrink: 0 }}>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Сессии ({sessions.length})</span>
            </div>
            {loading ? (
              <div className="loading"><div className="spinner" /> Загрузка...</div>
            ) : sessions.length === 0 ? (
              <div className="empty-state"><p>Нет сессий</p></div>
            ) : (
              sessions.map(s => (
                <div key={s.id}
                  onClick={() => selectSession(s)}
                  style={{
                    padding: '0.75rem',
                    cursor: 'pointer',
                    borderBottom: '1px solid #e5e7eb',
                    background: selectedSession?.id === s.id ? '#dbeafe' : 'white',
                  }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 500 }}>
                        <MessageSquare size={14} style={{ display: 'inline', marginRight: '0.25rem' }} />
                        Сессия #{s.id}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        <Clock size={12} style={{ display: 'inline', marginRight: '0.25rem' }} />
                        {new Date(s.last_activity_at).toLocaleString('ru-RU')}
                      </div>
                    </div>
                    <span className="badge badge-info">{channelLabel(s.channel)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div style={{ flex: 1 }}>
          {!selectedSession ? (
            <div className="card">
              <div className="empty-state">
                <MessageSquare size={48} color="#d1d5db" />
                <p>Выберите сессию для просмотра диалога</p>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="card-header">
                <span className="card-title">
                  Сессия #{selectedSession.id} &middot; {channelLabel(selectedSession.channel)}
                </span>
              </div>
              {messages.map(msg => (
                <div key={msg.id} style={{
                  padding: '0.75rem',
                  borderBottom: '1px solid #e5e7eb',
                  background: msg.role === 'user' ? '#f0f9ff' : '#fafafa',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
                        <strong>{msg.role === 'user' ? 'Пользователь' : 'ИИ'}</strong>
                        {' '}&middot;{' '}
                        {new Date(msg.created_at).toLocaleString('ru-RU')}
                        {msg.response_time_ms > 0 && ` (${msg.response_time_ms}мс)`}
                        {msg.feedback && (
                          <span className={`badge badge-${msg.feedback === 'useful' ? 'success' : 'danger'}`}
                            style={{ marginLeft: '0.5rem' }}>
                            {msg.feedback === 'useful' ? 'Полезно' : 'Не полезно'}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    </div>
                    {msg.trace && Object.keys(msg.trace).length > 0 && (
                      <button className="btn btn-outline btn-sm"
                        onClick={() => setTraceModal(msg.trace)}
                        style={{ marginLeft: '0.5rem', flexShrink: 0 }}>
                        <Eye size={14} /> Трейс
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {messages.length === 0 && (
                <div className="empty-state"><p>Нет сообщений</p></div>
              )}
            </div>
          )}
        </div>
      </div>

      {traceModal && (
        <div className="modal-overlay" onClick={() => setTraceModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '700px' }}>
            <h3 className="modal-title">Трассировка ответа</h3>
            <pre style={{
              background: '#f1f5f9', padding: '1rem', borderRadius: '0.5rem',
              fontSize: '0.8rem', overflow: 'auto', maxHeight: '60vh',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {JSON.stringify(traceModal, null, 2)}
            </pre>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setTraceModal(null)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
