import React, { useState, useRef, useEffect } from 'react'
import { Send, ThumbsUp, ThumbsDown } from 'lucide-react'
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
        id: Date.now() + 1,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message}`, id: Date.now() + 1 },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (messageId, feedback) => {
    try {
      await api.submitFeedback({ message_id: messageId, feedback })
      setMessages(prev =>
        prev.map(m => (m.id === messageId ? { ...m, feedback } : m))
      )
    } catch (err) {
      // ignore feedback errors
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>AI Chat</h1>
        <p>Ask questions about the knowledge base or request analytics</p>
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="empty-state">
              <MessageIcon />
              <p>Ask any question to the AI assistant</p>
              <p style={{ fontSize: '0.8rem', marginTop: '0.5rem', color: '#9ca3af' }}>
                Examples: "What ice cream products do we have?", "Show sales analytics",
                "Who are top managers?"
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`chat-message ${msg.role}`}>
              <div>
                <div className="chat-bubble">{msg.content}</div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="chat-sources">
                    Sources: {msg.sources.join(', ')}
                  </div>
                )}
                {msg.role === 'assistant' && !msg.feedback && (
                  <div className="chat-feedback">
                    <button onClick={() => handleFeedback(msg.id, 'useful')} title="Useful">
                      <ThumbsUp size={14} />
                    </button>
                    <button onClick={() => handleFeedback(msg.id, 'not_useful')} title="Not useful">
                      <ThumbsDown size={14} />
                    </button>
                  </div>
                )}
                {msg.feedback && (
                  <div className="chat-sources">
                    Feedback: {msg.feedback === 'useful' ? 'Useful' : 'Not useful'}
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
                  Thinking...
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
            placeholder="Type your question..."
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
