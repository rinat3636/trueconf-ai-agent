import React, { useState, useRef, useEffect } from 'react'
import { Send, ThumbsUp, ThumbsDown, FileText } from 'lucide-react'
import { api } from '../services/api'

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const messagesEnd = useRef(null)

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg = { role: 'user', content: input, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const data = await api.ask({ message: input, session_id: sessionId })
      setSessionId(data.session_id)
      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        rules_applied: data.rules_applied,
        confidence: data.confidence,
        message_id: data.message_id,
        id: data.message_id || Date.now() + 1,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Ошибка: ${err.message}`, id: Date.now() + 1 },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (msg, feedback) => {
    try {
      await api.submitFeedback({ message_id: msg.message_id || msg.id, feedback })
      setMessages(prev =>
        prev.map(m => (m.id === msg.id ? { ...m, feedback } : m))
      )
    } catch (err) {
      // ignore
    }
  }

  const startNewSession = () => {
    setMessages([])
    setSessionId(null)
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Чат с ИИ</h1>
          <p>Задавайте вопросы по базе знаний и аналитике</p>
        </div>
        {sessionId && (
          <button className="btn btn-outline" onClick={startNewSession}>Новый диалог</button>
        )}
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="empty-state">
              <MessageIcon />
              <p>Задайте вопрос ИИ-ассистенту</p>
              <p style={{ fontSize: '0.8rem', marginTop: '0.5rem', color: '#9ca3af' }}>
                Примеры: «Какие продукты есть в каталоге?», «Покажи аналитику продаж»,
                «Кто лучшие ТП?»
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`chat-message ${msg.role}`}>
              <div>
                <div className="chat-bubble">{msg.content}</div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="chat-sources">
                    <FileText size={12} style={{ display: 'inline', marginRight: '0.25rem' }} />
                    Источники: {msg.sources.join(', ')}
                  </div>
                )}
                {msg.rules_applied && msg.rules_applied.length > 0 && (
                  <div className="chat-sources">
                    Правила: {msg.rules_applied.join(', ')}
                  </div>
                )}
                {msg.confidence != null && msg.confidence > 0 && (
                  <div className="chat-sources">
                    Уверенность: {(msg.confidence * 100).toFixed(0)}%
                  </div>
                )}
                {msg.role === 'assistant' && !msg.feedback && (
                  <div className="chat-feedback">
                    <button onClick={() => handleFeedback(msg, 'useful')} title="Полезно">
                      <ThumbsUp size={14} />
                    </button>
                    <button onClick={() => handleFeedback(msg, 'not_useful')} title="Не полезно">
                      <ThumbsDown size={14} />
                    </button>
                  </div>
                )}
                {msg.feedback && (
                  <div className="chat-sources">
                    {msg.feedback === 'useful' ? 'Полезно' : 'Не полезно'}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-message assistant">
              <div className="chat-bubble">
                <div className="loading" style={{ padding: '0.25rem' }}>
                  <div className="spinner" style={{ width: '1rem', height: '1rem' }} />
                  Думаю...
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEnd} />
        </div>

        <form className="chat-input" onSubmit={handleSend}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Введите ваш вопрос..."
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  )
}

function MessageIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth="1.5">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}
