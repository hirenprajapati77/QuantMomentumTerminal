import React, { useState, useEffect } from 'react';
import './App.css';
import Dashboard from './pages/Dashboard';
import Scanner from './pages/Scanner';
import EliteSetups from './pages/EliteSetups';
import NearBreakout from './pages/NearBreakout';
import Backtest from './pages/Backtest';
import StockDetail from './pages/StockDetail';
import SettingsPage from './pages/Settings';
import { apiClient } from './api/client';
import { formatDate } from './utils/date';
import { 
  TrendingUp, 
  LayoutDashboard, 
  Flame, 
  Eye, 
  LineChart, 
  HelpCircle,
  Database,
  Settings as SettingsIcon
} from 'lucide-react';

export default function App() {
  const [activePage, setActivePage] = useState<string>('Dashboard');
  const [settingsToken, setSettingsToken] = useState<string | null>(null);
  const [pageParams, setPageParams] = useState<any>(null);
  const [lastScanDate, setLastScanDate] = useState<string>('Checking...');

  const fetchFreshness = async () => {
    try {
      const results = await apiClient.get('/scanner/results?limit=1');
      if (results && results.length > 0) {
        setLastScanDate(formatDate(results[0].date));
      } else {
        setLastScanDate('No scans run');
      }
    } catch (e) {
      setLastScanDate('Offline');
    }
  };

  useEffect(() => {
    fetchFreshness();
  }, [activePage]);

  const handleNavigate = (page: string, params: any = null) => {
    setActivePage(page);
    setPageParams(params);
  };

  const renderContent = () => {
    switch (activePage) {
      case 'Dashboard':
        return <Dashboard onNavigate={handleNavigate} />;
      case 'Scanner':
        return <Scanner onNavigate={handleNavigate} />;
      case 'EliteSetups':
        return <EliteSetups onNavigate={handleNavigate} />;
      case 'NearBreakout':
        return <NearBreakout onNavigate={handleNavigate} />;
      case 'Backtest':
        return <Backtest />;
      case 'Settings':
        return (
          <SettingsPage 
            token={settingsToken} 
            onUnlock={(token) => setSettingsToken(token)}
            onLock={() => {
              setSettingsToken(null);
              apiClient.setToken(null);
            }} 
          />
        );
      case 'StockDetail':
        return (
          <StockDetail 
            symbol={pageParams?.symbol || ''} 
            triggerDate={pageParams?.date}
            onBack={() => handleNavigate('Scanner')} 
          />
        );
      default:
        return <Dashboard onNavigate={handleNavigate} />;
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand-section">
          <TrendingUp className="brand-logo" />
          <span className="brand-name">ProTrader v5.0</span>
        </div>

        <nav style={{ flexGrow: 1 }}>
          <ul className="nav-list">
            <li 
              className={`nav-item ${activePage === 'Dashboard' ? 'active' : ''}`}
              onClick={() => handleNavigate('Dashboard')}
            >
              <LayoutDashboard className="nav-item-icon" />
              Dashboard
            </li>
            <li 
              className={`nav-item ${activePage === 'Scanner' ? 'active' : ''}`}
              onClick={() => handleNavigate('Scanner')}
            >
              <Database className="nav-item-icon" />
              Scanner Logs
            </li>
            <li 
              className={`nav-item ${activePage === 'EliteSetups' ? 'active' : ''}`}
              onClick={() => handleNavigate('EliteSetups')}
            >
              <Flame className="nav-item-icon" />
              Elite Setups
            </li>
            <li 
              className={`nav-item ${activePage === 'NearBreakout' ? 'active' : ''}`}
              onClick={() => handleNavigate('NearBreakout')}
            >
              <Eye className="nav-item-icon" />
              Near Breakout
            </li>
            <li 
              className={`nav-item ${activePage === 'Backtest' ? 'active' : ''}`}
              onClick={() => handleNavigate('Backtest')}
            >
              <LineChart className="nav-item-icon" />
              Backtesting
            </li>
            <li 
              className={`nav-item ${activePage === 'Settings' ? 'active' : ''}`}
              onClick={() => handleNavigate('Settings')}
            >
              <SettingsIcon className="nav-item-icon" />
              Settings
            </li>
          </ul>
        </nav>

        <div className="sidebar-footer">
          <div className="data-freshness-widget">
            <span>DATA FRESHNESS</span>
            <span className="data-freshness-time">{lastScanDate}</span>
          </div>
        </div>
      </aside>

      {/* Main Panel Content */}
      <main className="main-content">
        {renderContent()}
      </main>
    </div>
  );
}
