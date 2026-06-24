import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  MessageSquare, BookOpen, GraduationCap, Shield,
  BarChart3, Activity, Users, LogOut, LayoutDashboard,
  AlertTriangle, FileSearch, ClipboardList, X, Bot
} from 'lucide-react'

const ROLE_LABELS = {
  super_admin: 'Суперадмин',
  admin: 'Администратор',
  manager: 'Менеджер',
  employee: 'Сотрудник',
}

export default function Sidebar({ user, setUser, isOpen, onClose }) {
  const navigate = useNavigate()
  const isAdminOrSuper = ['super_admin', 'admin'].includes(user?.role)
  const isManagerPlus = ['super_admin', 'admin', 'manager'].includes(user?.role)
  const isSuperAdmin = user?.role === 'super_admin'

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
    navigate('/')
  }

  return (
    <div className={`sidebar ${isOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-logo">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Мир Мороженого AI</h2>
          <button className="sidebar-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <p>{user?.full_name || user?.username}</p>
        <p style={{ fontSize: '0.65rem', color: '#6b7280' }}>{ROLE_LABELS[user?.role] || user?.role}</p>
      </div>

      <div className="sidebar-section">Основное</div>
      <ul className="sidebar-nav">
        {isAdminOrSuper && (
          <li><NavLink to="/"><LayoutDashboard size={18} /> Панель</NavLink></li>
        )}
        <li><NavLink to="/chat"><MessageSquare size={18} /> Чат с ИИ</NavLink></li>
      </ul>

      {isAdminOrSuper && (
        <>
          <div className="sidebar-section">База знаний</div>
          <ul className="sidebar-nav">
            <li><NavLink to="/knowledge"><BookOpen size={18} /> Документы</NavLink></li>
            <li><NavLink to="/training"><GraduationCap size={18} /> Обучение</NavLink></li>
            <li><NavLink to="/moderation"><Shield size={18} /> Модерация</NavLink></li>
            <li><NavLink to="/conflicts"><AlertTriangle size={18} /> Конфликты</NavLink></li>
          </ul>

          <div className="sidebar-section">Аналитика</div>
          <ul className="sidebar-nav">
            <li><NavLink to="/sales"><BarChart3 size={18} /> Продажи</NavLink></li>
            <li><NavLink to="/chats"><FileSearch size={18} /> История чатов</NavLink></li>
          </ul>

          <div className="sidebar-section">Система</div>
          <ul className="sidebar-nav">
            <li><NavLink to="/bot-settings"><Bot size={18} /> Настройки TrueConf</NavLink></li>
            <li><NavLink to="/monitoring"><Activity size={18} /> Мониторинг</NavLink></li>
            <li><NavLink to="/audit"><ClipboardList size={18} /> Аудит</NavLink></li>
            {isSuperAdmin && (
              <li><NavLink to="/users"><Users size={18} /> Пользователи</NavLink></li>
            )}
          </ul>
        </>
      )}

      {!isAdminOrSuper && isManagerPlus && (
        <>
          <div className="sidebar-section">Аналитика</div>
          <ul className="sidebar-nav">
            <li><NavLink to="/sales"><BarChart3 size={18} /> Продажи</NavLink></li>
          </ul>
        </>
      )}

      <ul className="sidebar-nav" style={{ marginTop: 'auto', borderTop: '1px solid #374151', paddingTop: '1rem' }}>
        <li><button onClick={handleLogout}><LogOut size={18} /> Выход</button></li>
      </ul>
    </div>
  )
}
