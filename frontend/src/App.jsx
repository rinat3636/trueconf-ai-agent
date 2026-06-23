import React, { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import Sidebar from './components/Sidebar'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ChatPage from './pages/ChatPage'
import ChatViewerPage from './pages/ChatViewerPage'
import KnowledgePage from './pages/KnowledgePage'
import TrainingPage from './pages/TrainingPage'
import ModerationPage from './pages/ModerationPage'
import ConflictsPage from './pages/ConflictsPage'
import SalesPage from './pages/SalesPage'
import MonitoringPage from './pages/MonitoringPage'
import UsersPage from './pages/UsersPage'
import AuditPage from './pages/AuditPage'

function hasRole(user, roles) {
  return roles.includes(user?.role)
}

export default function App() {
  const [user, setUser] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const saved = localStorage.getItem('user')
    if (saved) {
      try { setUser(JSON.parse(saved)) } catch { /* ignore */ }
    }
  }, [])

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  if (!user) {
    return <LoginPage onLogin={setUser} />
  }

  const isAdminOrSuper = hasRole(user, ['super_admin', 'admin'])
  const isManagerPlus = hasRole(user, ['super_admin', 'admin', 'manager'])
  const isSuperAdmin = user.role === 'super_admin'

  return (
    <div className="layout">
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}
      <Sidebar user={user} setUser={setUser} isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="main-content">
        <div className="mobile-header">
          <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
          <span className="mobile-header-title">Мир Мороженого AI</span>
        </div>
        <Routes>
          <Route path="/" element={isAdminOrSuper ? <DashboardPage /> : <Navigate to="/chat" />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chats" element={isAdminOrSuper ? <ChatViewerPage /> : <Navigate to="/chat" />} />
          <Route path="/knowledge" element={isAdminOrSuper ? <KnowledgePage /> : <Navigate to="/chat" />} />
          <Route path="/training" element={isAdminOrSuper ? <TrainingPage /> : <Navigate to="/chat" />} />
          <Route path="/moderation" element={isAdminOrSuper ? <ModerationPage /> : <Navigate to="/chat" />} />
          <Route path="/conflicts" element={isAdminOrSuper ? <ConflictsPage /> : <Navigate to="/chat" />} />
          <Route path="/sales" element={isManagerPlus ? <SalesPage /> : <Navigate to="/chat" />} />
          <Route path="/monitoring" element={isAdminOrSuper ? <MonitoringPage /> : <Navigate to="/chat" />} />
          <Route path="/users" element={isSuperAdmin ? <UsersPage /> : <Navigate to="/chat" />} />
          <Route path="/audit" element={isAdminOrSuper ? <AuditPage /> : <Navigate to="/chat" />} />
          <Route path="*" element={<Navigate to={isAdminOrSuper ? "/" : "/chat"} />} />
        </Routes>
      </div>
    </div>
  )
}
