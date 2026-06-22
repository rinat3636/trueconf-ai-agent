import React, { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import KnowledgePage from './pages/KnowledgePage'
import TrainingPage from './pages/TrainingPage'
import ModerationPage from './pages/ModerationPage'
import SalesPage from './pages/SalesPage'
import MonitoringPage from './pages/MonitoringPage'
import UsersPage from './pages/UsersPage'
import TrueConfPage from './pages/TrueConfPage'

export default function App() {
  const [user, setUser] = useState(null)

  useEffect(() => {
    const saved = localStorage.getItem('user')
    if (saved) {
      try { setUser(JSON.parse(saved)) } catch { /* ignore */ }
    }
  }, [])

  if (!user) {
    return <LoginPage onLogin={setUser} />
  }

  const isAdmin = user.role === 'admin'

  return (
    <div className="layout">
      <Sidebar user={user} />
      <div className="main-content">
        <Routes>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/knowledge" element={isAdmin ? <KnowledgePage /> : <Navigate to="/chat" />} />
          <Route path="/training" element={isAdmin ? <TrainingPage /> : <Navigate to="/chat" />} />
          <Route path="/moderation" element={isAdmin ? <ModerationPage /> : <Navigate to="/chat" />} />
          <Route path="/sales" element={isAdmin ? <SalesPage /> : <Navigate to="/chat" />} />
          <Route path="/monitoring" element={isAdmin ? <MonitoringPage /> : <Navigate to="/chat" />} />
          <Route path="/users" element={isAdmin ? <UsersPage /> : <Navigate to="/chat" />} />
          <Route path="/trueconf" element={isAdmin ? <TrueConfPage /> : <Navigate to="/chat" />} />
          <Route path="*" element={<Navigate to="/chat" />} />
        </Routes>
      </div>
    </div>
  )
}
