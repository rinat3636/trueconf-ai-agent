import React, { useState, useRef, useEffect } from 'react'
import { Send, ThumbsUp, ThumbsDown, FileText, Bot, User, Plus, Sparkles } from 'lucide-react'
import { api } from '../services/api'

const SUGGESTIONS = [
  'Какие продукты есть в каталоге?',
  'Покажи аналитику продаж',
  'Кто лучшие торговые представители?',
  'Условия хранения мороженого',
]

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const messagesEnd = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = async (e) => {
    e?.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    const userMsg = { role: 'user', content: text, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const data = await api.ask({ message: text, session_id: sessionId })
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
        { role: 'assistant', content: `Ошибка: ${err.message}`, id: Date.now() + 1, isError: true },
      ])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleSuggestion = (text) => {
    setInput(text)
    setTimeout(() => {
      const fakeEvent = { preventDefault: () => {} }
      setInput('')
      const userMsg = { role: 'user', content: text, id: Date.now() }
      setMessages(prev => [...prev, userMsg])
      setLoading(true)
      api.ask({ message: text, session_id: sessionId }).then(data => {
        setSessionId(data.session_id)
        setMessages(prev => [...prev, {
          role: 'assistant', content: data.answer, sources: data.sources,
          rules_applied: data.rules_applied, confidence: data.confidence,
          message_id: data.message_id, id: data.message_id || Date.now() + 1,
        }])
      }).catch(err => {
        setMessages(prev => [...prev, { role: 'assistant', content: `Ошибка: ${err.message}`, id: Date.now() + 1, isError: true }])
      }).finally(() => setLoading(false))
    }, 0)
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
    inputRef.current?.focus()
  }

  return (
    <div className="chat-page">
      <div className="chat-page-header">
        <div className="chat-page-header-left">
          <div className="chat-page-avatar">
            <Bot size={20} />
          </div>
          <div>
            <h1>Чат с ИИ</h1>
            <p>Ассистент по базе знаний и аналитике</p>
          </div>
        </div>
        {sessionId && (
          <button className="chat-new-btn" onClick={startNewSession}>
            <Plus size={16} />
            <span>Новый диалог</span>
          </button>
        )}
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-welcome">
              <div className="chat-welcome-icon">
                <Sparkles size={32} />
              </div>
              <h2>Добро пожаловать!</h2>
              <p>Я ИИ-ассистент компании «Мир Мороженого». Задайте мне вопрос по базе знаний, аналитике продаж или продуктам.</p>
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} className="chat-suggestion-btn" onClick={() => handleSuggestion(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`chat-msg ${msg.role} ${msg.isError ? 'error' : ''}`}>
              <div className="chat-msg-avatar">
                {msg.role === 'user' ? <User size={18} /> : <Bot size={18} />}
              </div>
              <div className="chat-msg-body">
                <div className="chat-msg-name">
                  {msg.role === 'user' ? 'Вы' : 'ИИ Ассистент'}
                </div>
                <div className="chat-msg-bubble">{msg.content}</div>

                {msg.sources && msg.sources.length > 0 && (
                  <div className="chat-msg-meta">
                    <FileText size={12} />
                    <span>Источники: {msg.sources.map(s => s.document_title || s.title || 'База знаний').join(', ')}</span>
                  </div>
                )}
                {msg.rules_applied && msg.rules_applied.length > 0 && (
                  <div className="chat-msg-meta">
                    <span>Правила: {msg.rules_applied.map(r => r.title || r.rule_type || r).join(', ')}</span>
                  </div>
                )}
                {msg.confidence != null && msg.confidence > 0 && (
                  <div className="chat-msg-meta">
                    <span>Уверенность: {(msg.confidence * 100).toFixed(0)}%</span>
                  </div>
                )}

                {msg.role === 'assistant' && !msg.feedback && !msg.isError && (
                  <div className="chat-msg-actions">
                    <button className="chat-action-btn" onClick={() => handleFeedback(msg, 'useful')} title="Полезно">
                      <ThumbsUp size={14} />
                    </button>
                    <button className="chat-action-btn" onClick={() => handleFeedback(msg, 'not_useful')} title="Не полезно">
                      <ThumbsDown size={14} />
                    </button>
                  </div>
                )}
                {msg.feedback && (
                  <div className="chat-msg-meta">
                    <span className={`chat-feedback-label ${msg.feedback === 'useful' ? 'positive' : 'negative'}`}>
                      {msg.feedback === 'useful' ? 'Полезно' : 'Не полезно'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-msg assistant">
              <div className="chat-msg-avatar">
                <Bot size={18} />
              </div>
              <div className="chat-msg-body">
                <div className="chat-msg-name">ИИ Ассистент</div>
                <div className="chat-msg-bubble">
                  <div className="chat-typing">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEnd} />
        </div>

        <form className="chat-input-bar" onSubmit={handleSend}>
          <div className="chat-input-wrapper">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Введите ваш вопрос..."
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()} className="chat-send-btn">
              <Send size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
