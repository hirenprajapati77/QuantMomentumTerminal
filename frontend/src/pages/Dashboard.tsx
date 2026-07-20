import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { formatDate } from '../utils/date';
import { RefreshCw, Flame, Layers, HelpCircle, Activity, Clock, AlertTriangle } from 'lucide-react';

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
  const [dataHealth, setDataHealth] = useState<any>(null);

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
        setLastScanDate(formatDate(latestDate));

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

      try {
        const health = await apiClient.get('/scanner/data-health');
        setDataHealth(health);
      } catch (err) {
        setDataHealth(null);
      }
    } catch (e: any) {
      console.error("Failed to load dashboard data", e);
    }
  };

  useEffect(() => {
    loadData();

    // Check if a scan is already running when page loads
    apiClient.get('/scanner/status').then((res: any) => {
      if (res && res.is_running) {
        setLoadingScan(true);
        setScanMessage('A scan is currently in progress. Monitoring progress...');
        pollScanStatus();
      }
    }).catch(() => {});
  }, []);

  const pollScanStatus = async () => {
    const pollInterval = setInterval(async () => {
      try {
        const res = await apiClient.get('/scanner/status');
        if (res && !res.is_running) {
          clearInterval(pollInterval);
          setScanMessage('Ingest + scan completed. Check Active Signals and data freshness.');
          setLoadingScan(false);
          loadData();
        }
      } catch (err) {
        clearInterval(pollInterval);
        setScanMessage('Failed to verify scan status.');
        setLoadingScan(false);
      }
    }, 3000);
  };

  const handleManualScan = async () => {
    setLoadingScan(true);
    setScanMessage('Catch-up ingestion + scan in progress (may take several minutes)...');
    try {
      // Default API mode downloads missing candles before scoring
      await apiClient.post('/scanner/scan', { ingest: true });
      // Begin polling the background task status
      pollScanStatus();
    } catch (e: any) {
      const msg = String(e.message || e.detail || '').toLowerCase();
      if (e.status === 409 || msg.includes('409') || msg.includes('already in progress')) {
        setScanMessage('A scan is already in progress. Monitoring progress...');
        pollScanStatus();
      } else {
        setScanMessage(`Scan failed: ${e.message || 'Unknown error'}`);
        setLoadingScan(false);
      }
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

      {dataHealth?.warning && (
        <div className="glass-panel" style={{
          padding: '16px 20px',
          marginBottom: '24px',
          borderColor: 'var(--danger)',
          display: 'flex',
          gap: '12px',
          alignItems: 'flex-start'
        }}>
          <AlertTriangle size={20} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong style={{ color: '#fff' }}>Data pipeline warning</strong>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: 4 }}>
              {dataHealth.warning}
            </p>
            {dataHealth.last_candle_date && (
              <p style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: 6 }}>
                Last candle: {formatDate(dataHealth.last_candle_date)} · Scoreable symbols:{' '}
                {dataHealth.symbols_with_min_history}/{dataHealth.active_symbols}
              </p>
            )}
          </div>
        </div>
      )}

      <div className="stats-grid">
        <div className="glass-panel stat-card">
          <div className="stat-header">
            <span>DATA FRESHNESS</span>
            <Activity size={18} className="text-muted" />
          </div>
          <div className="stat-value">{lastScanDate}</div>
          <div className="stat-desc">
            {dataHealth?.last_candle_date
              ? `Last candle ${formatDate(dataHealth.last_candle_date)}`
              : 'Latest daily scan database date'}
          </div>
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
          <div className="stat-desc">
            {dataHealth
              ? `${dataHealth.symbols_with_min_history} scoreable (≥${dataHealth.min_history_candles} bars)`
              : 'Stocks filtered by hard liquidity rules'}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px', marginTop: '40px' }}>
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 className="brand-name" style={{ marginBottom: '16px', fontSize: '18px' }}>Operator Control</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px', lineHeight: '1.6' }}>
            Trigger catch-up ingestion + scan: downloads missing Fyers/NSE candles for stalled days,
            repairs short-history symbols, then recomputes grades and entry signals.
          </p>
          <button
            className="btn btn-primary"
            onClick={handleManualScan}
            disabled={loadingScan}
          >
            {loadingScan ? <RefreshCw className="spinner" size={16} /> : <RefreshCw size={16} />}
            Trigger Ingest + Scan
          </button>
          {scanMessage && (
            <p style={{
              marginTop: '16px',
              fontSize: '13px',
              fontWeight: 500,
              color: scanMessage.includes('completed') ? 'var(--success)' : (scanMessage.includes('progress') ? 'var(--text-secondary)' : 'var(--danger)')
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
