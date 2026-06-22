import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  MessageSquare, BookOpen, GraduationCap, Shield,
  BarChart3, Activity, Users, LogOut, Settings
} from 'lucide-react'

export default function Sidebar({ user }) {
  const navigate = useNavigate()
  const isAdmin = user?.role === 'admin'

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <h2>TrueConf AI</h2>
        <p>{user?.full_name || user?.username} ({user?.role})</p>
      </div>

      <div className="sidebar-section">Main</div>
      <ul className="sidebar-nav">
        <li><NavLink to="/chat"><MessageSquare size={18} /> Chat</NavLink></li>
      </ul>

      {isAdmin && (
        <>
          <div className="sidebar-section">Knowledge Base</div>
          <ul className="sidebar-nav">
            <li><NavLink to="/knowledge"><BookOpen size={18} /> Documents</NavLink></li>
            <li><NavLink to="/training"><GraduationCap size={18} /> Training</NavLink></li>
            <li><NavLink to="/moderation"><Shield size={18} /> Moderation</NavLink></li>
          </ul>

          <div className="sidebar-section">Analytics</div>
          <ul className="sidebar-nav">
            <li><NavLink to="/sales"><BarChart3 size={18} /> Sales</NavLink></li>
            <li><NavLink to="/monitoring"><Activity size={18} /> Monitoring</NavLink></li>
          </ul>

          <div className="sidebar-section">System</div>
          <ul className="sidebar-nav">
            <li><NavLink to="/users"><Users size={18} /> Users</NavLink></li>
          </ul>
        </>
      )}

      <ul className="sidebar-nav" style={{ marginTop: 'auto', borderTop: '1px solid #374151', paddingTop: '1rem' }}>
        <li><button onClick={handleLogout}><LogOut size={18} /> Logout</button></li>
      </ul>
    </div>
  )
}
