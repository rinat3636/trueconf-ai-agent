import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'
import { Bot, Power, PowerOff, RefreshCw, Send, Wifi, WifiOff, MessageSquare } from 'lucide-react'

export default function TrueConfPage() {
  const [status, setStatus] = useState(null)
  const [chats, setChats] = useState([])
  const [testResult, setTestResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState('')
  const [sendChat, setSendChat] = useState('')
  const [sendText, setSendText] = useState('')
  const [sendResult, setSendResult] = useState(null)

  const loadStatus = useCallback(async () => {
    try {
      const data = await api.getTrueConfStatus()
      setStatus(data)
    } catch (e) {
      setStatus({ enabled: false, connected: false, running: false, error: e.message })
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 10000)
    return () => clearInterval(interval)
  }, [loadStatus])

  const handleStart = async () => {
    setActionLoading('start')
    try {
      await api.startTrueConfBot()
      await loadStatus()
    } catch (e) {
      alert('Error: ' + e.message)
    }
    setActionLoading('')
  }

  const handleStop = async () => {
    setActionLoading('stop')
    try {
      await api.stopTrueConfBot()
      await loadStatus()
    } catch (e) {
      alert('Error: ' + e.message)
    }
    setActionLoading('')
  }

  const handleTest = async () => {
    setActionLoading('test')
    setTestResult(null)
    try {
      const result = await api.testTrueConfConnection()
      setTestResult(result)
    } catch (e) {
      setTestResult({ status: 'error', error: e.message })
    }
    setActionLoading('')
  }

  const handleLoadChats = async () => {
    setActionLoading('chats')
    try {
      const data = await api.getTrueConfChats()
      setChats(data.chats || [])
    } catch (e) {
      alert('Error: ' + e.message)
    }
    setActionLoading('')
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!sendChat.trim() || !sendText.trim()) return
    setActionLoading('send')
    setSendResult(null)
    try {
      const result = await api.sendTrueConfMessage({ chat_id: sendChat, text: sendText })
      setSendResult(result)
      setSendText('')
    } catch (e) {
      setSendResult({ status: 'error', error: e.message })
    }
    setActionLoading('')
  }

  if (loading) return <div className="page-loading">Loading...</div>

  return (
    <div className="page">
      <div className="page-header">
        <h1><Bot size={24} /> TrueConf Bot</h1>
        <button className="btn btn-secondary" onClick={loadStatus}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Status</div>
          <div className="stat-value">
            {status?.running ? (
              <span style={{ color: '#10b981' }}><Wifi size={18} /> Running</span>
            ) : (
              <span style={{ color: '#ef4444' }}><WifiOff size={18} /> Stopped</span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Connected</div>
          <div className="stat-value" style={{ color: status?.connected ? '#10b981' : '#ef4444' }}>
            {status?.connected ? 'Yes' : 'No'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Server</div>
          <div className="stat-value" style={{ fontSize: '0.9rem' }}>{status?.server_url || '-'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Bot User</div>
          <div className="stat-value" style={{ fontSize: '0.9rem' }}>{status?.bot_user || '-'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Active Chats</div>
          <div className="stat-value">{status?.active_chats || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Poll Interval</div>
          <div className="stat-value">{status?.poll_interval || 0}s</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: '1.5rem' }}>
        <h3>Bot Controls</h3>
        <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
          <button
            className="btn btn-primary"
            onClick={handleStart}
            disabled={actionLoading === 'start' || status?.running}
          >
            <Power size={16} /> {actionLoading === 'start' ? 'Starting...' : 'Start Bot'}
          </button>
          <button
            className="btn btn-danger"
            onClick={handleStop}
            disabled={actionLoading === 'stop' || !status?.running}
          >
            <PowerOff size={16} /> {actionLoading === 'stop' ? 'Stopping...' : 'Stop Bot'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleTest}
            disabled={actionLoading === 'test'}
          >
            <Wifi size={16} /> {actionLoading === 'test' ? 'Testing...' : 'Test Connection'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleLoadChats}
            disabled={actionLoading === 'chats'}
          >
            <MessageSquare size={16} /> {actionLoading === 'chats' ? 'Loading...' : 'Load Chats'}
          </button>
        </div>

        {testResult && (
          <div style={{
            marginTop: '1rem',
            padding: '1rem',
            borderRadius: '8px',
            background: testResult.authenticated ? '#ecfdf5' : '#fef2f2',
            border: `1px solid ${testResult.authenticated ? '#10b981' : '#ef4444'}`,
          }}>
            <strong>Connection Test: </strong>
            {testResult.authenticated ? (
              <span style={{ color: '#10b981' }}>Connected successfully</span>
            ) : (
              <span style={{ color: '#ef4444' }}>
                Failed: {testResult.error || 'Could not authenticate'}
              </span>
            )}
            {testResult.bot_user && (
              <pre style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
                {JSON.stringify(testResult.bot_user, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>

      {chats.length > 0 && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <h3>Active Chats ({chats.length})</h3>
          <table className="table" style={{ marginTop: '1rem' }}>
            <thead>
              <tr>
                <th>Chat ID</th>
                <th>Type</th>
                <th>Name</th>
              </tr>
            </thead>
            <tbody>
              {chats.map((chat, i) => (
                <tr key={i}>
                  <td>{chat.id || chat.chat_id || '-'}</td>
                  <td>{chat.type || '-'}</td>
                  <td>{chat.name || chat.display_name || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card" style={{ marginTop: '1.5rem' }}>
        <h3>Send Message</h3>
        <form onSubmit={handleSend} style={{ marginTop: '1rem' }}>
          <div className="form-group">
            <label>Chat ID / User ID</label>
            <input
              type="text"
              className="form-control"
              value={sendChat}
              onChange={e => setSendChat(e.target.value)}
              placeholder="e.g. user@trueconf.local or chat ID"
            />
          </div>
          <div className="form-group" style={{ marginTop: '0.75rem' }}>
            <label>Message</label>
            <textarea
              className="form-control"
              value={sendText}
              onChange={e => setSendText(e.target.value)}
              placeholder="Enter message..."
              rows={3}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={actionLoading === 'send' || !sendChat.trim() || !sendText.trim()}
            style={{ marginTop: '0.75rem' }}
          >
            <Send size={16} /> {actionLoading === 'send' ? 'Sending...' : 'Send'}
          </button>
          {sendResult && (
            <span style={{
              marginLeft: '1rem',
              color: sendResult.status === 'sent' ? '#10b981' : '#ef4444',
            }}>
              {sendResult.status === 'sent' ? 'Message sent!' : `Error: ${sendResult.error || 'Failed'}`}
            </span>
          )}
        </form>
      </div>

      <div className="card" style={{ marginTop: '1.5rem' }}>
        <h3>Setup Guide</h3>
        <div style={{ marginTop: '0.75rem', lineHeight: '1.8' }}>
          <ol>
            <li>
              Create an OAuth2 application in TrueConf Server Admin Panel:
              <br />
              <code>Admin Panel &rarr; Web &rarr; OAuth2 Applications &rarr; Add</code>
            </li>
            <li>
              Set redirect URI: <code>https://localhost/</code>
            </li>
            <li>
              Copy <strong>Client ID</strong> and <strong>Client Secret</strong> to <code>.env</code>
            </li>
            <li>
              Create a bot user account in TrueConf Server and set its username and password in <code>.env</code>
            </li>
            <li>
              Set <code>TRUECONF_ENABLED=true</code> in <code>.env</code> and restart the backend
            </li>
          </ol>
        </div>
      </div>
    </div>
  )
}
