import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { RefreshCw, Flame, Layers, HelpCircle, Activity, Clock } from 'lucide-react';

interface Props {
  onNavigate: (page: string, params?: any) => void;
}

export default function Dashboard({ onNavigate }: Props) {
  const [universeStats, setUniverseStats] = useState<any>({ total: 0, active: 0 });
  const [lastScanDate, setLastScanDate] = useState<string>('None');
  const [lastScanTimestamp, setLastScanTimestamp] = useState<string>('Checking...');
  const [activeSignalsCount, setActiveSignalsCount] = useState<number>(0);
  const [loadingScan, setLoadingScan] = useState(false);
  const [scanMessage, setScanMessage] = useState('');

  const loadData = async () => {
    try {
      // Load Universe stats
      const universe = await apiClient.get('/universe/constituents');
      if (universe && universe.summary) {
        setUniverseStats({
          total: universe.summary.total_constituents,
          active: universe.summary.active_constituents
        });
      }

      // Load last scan date and count active triggers
      const results = await apiClient.get('/scanner/results');
      if (results && results.length > 0) {
        const latestDate = results[0].date;
        setLastScanDate(latestDate);

        // Count how many entry signals were triggered on the latest scan date
        const count = results.filter((r: any) => r.date === latestDate && r.entry_triggered).length;
        setActiveSignalsCount(count);
      } else {
        setLastScanDate('None');
        setActiveSignalsCount(0);
      }

      // Load last run execution timestamp
      try {
        const lastRun = await apiClient.get('/scanner/last-run');
        if (lastRun && lastRun.timestamp) {
          const date = new Date(lastRun.timestamp * 1000);
          const formatted = date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
          });
          setLastScanTimestamp(formatted);
        } else {
          setLastScanTimestamp('No scans run yet');
        }
      } catch (err) {
        setLastScanTimestamp('No scans run yet');
      }
    } catch (e: any) {
      console.error("Failed to load dashboard data", e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleManualScan = async () => {
    setLoadingScan(true);
    setScanMessage('Scanning in progress...');
    try {
      await apiClient.post('/scanner/scan', {});
      setScanMessage('Scan completed successfully!');
      loadData();
    } catch (e: any) {
      setScanMessage(`Scan failed: ${e.message}`);
    } finally {
      setLoadingScan(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Quant Momentum Terminal</h1>
          <p className="page-subtitle">Multi-stage relative strength and volume breakouts scanner for Indian Equities.</p>
        </div>
      </div>

      <div className="stats-grid">
        <div className="glass-panel stat-card">
          <div className="stat-header">
            <span>DATA FRESHNESS</span>
            <Activity size={18} className="text-muted" />
          </div>
          <div className="stat-value">{lastScanDate}</div>
          <div className="stat-desc">Latest daily scan database date</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-header">
            <span>LAST COMPLETED SCAN</span>
            <Clock size={18} className="text-muted" />
          </div>
          <div className="stat-value" style={{ fontSize: '18px', lineHeight: '1.4', marginTop: '10px' }}>
            {lastScanTimestamp}
          </div>
          <div className="stat-desc">Exact execution timestamp</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-header">
            <span>ACTIVE SIGNALS</span>
            <Flame size={18} style={{ color: activeSignalsCount > 0 ? 'var(--success)' : 'var(--text-muted)' }} />
          </div>
          <div className="stat-value">{activeSignalsCount} Setups</div>
          <div className="stat-desc">Elite/A+ triggers on the latest date</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-header">
            <span>ACTIVE UNIVERSE</span>
            <Layers size={18} className="text-muted" />
          </div>
          <div className="stat-value">{universeStats.active} / {universeStats.total}</div>
          <div className="stat-desc">Stocks filtered by hard liquidity rules</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px', marginTop: '40px' }}>
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 className="brand-name" style={{ marginBottom: '16px', fontSize: '18px' }}>Operator Control</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px', lineHeight: '1.6' }}>
            Run a manual database update scan to download the latest NSE Bhavcopy files, calculate indicators, and compute grades for today.
          </p>
          <button
            className="btn btn-primary"
            onClick={handleManualScan}
            disabled={loadingScan}
          >
            {loadingScan ? <RefreshCw className="spinner" size={16} /> : <RefreshCw size={16} />}
            Trigger Daily Scan
          </button>
          {scanMessage && (
            <p style={{
              marginTop: '16px',
              fontSize: '13px',
              fontWeight: 500,
              color: scanMessage.includes('completed') ? 'var(--success)' : 'var(--danger)'
            }}>
              {scanMessage}
            </p>
          )}
        </div>

        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 className="brand-name" style={{ marginBottom: '16px', fontSize: '18px' }}>Strategy Methodology</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '14px', lineHeight: '1.5' }}>
            <div style={{ display: 'flex', gap: '12px' }}>
              <HelpCircle size={20} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              <div>
                <strong style={{ color: '#fff' }}>Vol Contraction (VCP)</strong>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Identifies tight consolidations under declining volatility leg-by-leg (declining ATR).</p>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <HelpCircle size={20} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              <div>
                <strong style={{ color: '#fff' }}>Relative Strength (RS)</strong>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Scored via percentile rankings against the universe across 20, 50, and 100 days.</p>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <HelpCircle size={20} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              <div>
                <strong style={{ color: '#fff' }}>Central Pivot Range (CPR)</strong>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Gates entries by requiring a narrow consolidation prior to a daily range breakout.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
