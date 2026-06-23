import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { Play, Clipboard, HelpCircle, CheckCircle, AlertTriangle, Layers } from 'lucide-react';

export default function Backtest() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [activeJob, setActiveJob] = useState<any>(null);
  const [activeJobTrades, setActiveJobTrades] = useState<any[]>([]);
  const [loadingTrades, setLoadingTrades] = useState(false);

  // Form parameters
  const [scoreThreshold, setScoreThreshold] = useState(85.0);
  const [timeStopDays, setTimeStopDays] = useState(30);
  const [initialCapital, setInitialCapital] = useState(1000000);
  const [running, setRunning] = useState(false);
  const [runMessage, setRunMessage] = useState('');

  const loadJobs = async (selectFirst = false) => {
    try {
      const data = await apiClient.get('/backtest/jobs');
      setJobs(data);
      if (selectFirst && data.length > 0) {
        handleSelectJob(data[0]);
      }
    } catch (e) {
      console.error("Failed to load backtest jobs", e);
    } finally {
      setLoadingJobs(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleSelectJob = async (job: any) => {
    setActiveJob(job);
    if (job.status === 'COMPLETED') {
      setLoadingTrades(true);
      try {
        const trades = await apiClient.get(`/backtest/jobs/${job.id}/trades`);
        setActiveJobTrades(trades);
        
        // Plot equity curve after a short tick to let DOM update
        setTimeout(() => {
          plotEquityCurve(job.metrics);
        }, 100);
      } catch (e) {
        console.error("Failed to load trades", e);
      } finally {
        setLoadingTrades(false);
      }
    } else {
      setActiveJobTrades([]);
    }
  };

  const plotEquityCurve = (metrics: any) => {
    if (!metrics || !metrics.equity_curve || metrics.equity_curve.length === 0) return;
    
    const dates = metrics.equity_curve.map((e: any) => e.date);
    const equities = metrics.equity_curve.map((e: any) => e.equity);

    const trace = {
      x: dates,
      y: equities,
      type: 'scatter',
      mode: 'lines',
      name: 'Equity Curve',
      line: {
        color: '#38bdf8',
        width: 2.5
      },
      fill: 'tozeroy',
      fillcolor: 'rgba(56, 189, 248, 0.05)'
    };

    const layout = {
      paper_bgcolor: 'rgba(0, 0, 0, 0)',
      plot_bgcolor: 'rgba(0, 0, 0, 0)',
      font: {
        family: 'Inter, sans-serif',
        color: '#94a3b8'
      },
      margin: { t: 20, r: 20, b: 40, l: 60 },
      xaxis: {
        gridcolor: 'rgba(255, 255, 255, 0.04)',
        linecolor: 'rgba(255, 255, 255, 0.08)'
      },
      yaxis: {
        gridcolor: 'rgba(255, 255, 255, 0.04)',
        linecolor: 'rgba(255, 255, 255, 0.08)',
        tickformat: '$,.0f' // comma separated format
      }
    };

    const config = {
      responsive: true,
      displayModeBar: false
    };

    const Plotly = (window as any).Plotly;
    if (Plotly) {
      Plotly.newPlot('equity-chart-container', [trace], layout, config);
    }
  };

  const handleRunBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setRunMessage('Queuing backtest execution...');
    try {
      const newJob = await apiClient.post('/backtest/run', {
        score_threshold: scoreThreshold,
        time_stop_days: timeStopDays,
        initial_capital: initialCapital
      });
      setRunMessage(`Backtest started! Job ID: ${newJob.id.slice(0, 8)}`);
      
      // Reload jobs list and auto-select the running job
      await loadJobs();
      handleSelectJob(newJob);
      
      // Start polling for completion
      startPolling(newJob.id);
    } catch (e: any) {
      setRunMessage(`Run failed: ${e.message}`);
      setRunning(false);
    }
  };

  const startPolling = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const job = await apiClient.get(`/backtest/jobs/${jobId}`);
        if (job.status === 'COMPLETED' || job.status === 'FAILED') {
          clearInterval(interval);
          setRunning(false);
          loadJobs();
          handleSelectJob(job);
        } else {
          // Update status of currently viewed job if it's the one running
          setActiveJob(job);
        }
      } catch (e) {
        clearInterval(interval);
        setRunning(false);
      }
    }, 3000);
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Backtesting Simulator</h1>
          <p className="page-subtitle">Run historical event-driven simulation over 5 years of daily Bhavcopy history.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '32px' }}>
        {/* Left Side: Parameters Form and History list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 className="brand-name" style={{ fontSize: '18px', marginBottom: '20px' }}>Simulation Parameters</h3>
            <form onSubmit={handleRunBacktest}>
              <div className="form-group">
                <label className="form-label">Min Score Threshold</label>
                <input
                  type="number"
                  step="0.5"
                  className="form-input"
                  value={scoreThreshold}
                  onChange={e => setScoreThreshold(parseFloat(e.target.value))}
                  required
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Use 85.0 for standard strategy, 60.0 to audit mechanics.
                </span>
              </div>

              <div className="form-group">
                <label className="form-label">Time Stop (Trading Days)</label>
                <input
                  type="number"
                  className="form-input"
                  value={timeStopDays}
                  onChange={e => setTimeStopDays(parseInt(e.target.value))}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Initial Capital (Rs.)</label>
                <input
                  type="number"
                  className="form-input"
                  value={initialCapital}
                  onChange={e => setInitialCapital(parseFloat(e.target.value))}
                  required
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '10px' }}
                disabled={running}
              >
                <Play size={16} /> {running ? 'Running Backtest...' : 'Execute Backtest'}
              </button>
            </form>
            {runMessage && (
              <p style={{ marginTop: '16px', fontSize: '13px', color: 'var(--primary)', textAlign: 'center' }}>
                {runMessage}
              </p>
            )}
          </div>

          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 className="brand-name" style={{ fontSize: '18px', marginBottom: '16px' }}>Simulation History</h3>
            {loadingJobs ? (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                Loading jobs...
              </div>
            ) : jobs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '13px' }}>
                No past backtests found.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '320px', overflowY: 'auto' }}>
                {jobs.map((job) => (
                  <div
                    key={job.id}
                    onClick={() => handleSelectJob(job)}
                    style={{
                      padding: '12px',
                      borderRadius: '8px',
                      background: activeJob && activeJob.id === job.id ? 'rgba(56, 189, 248, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                      border: activeJob && activeJob.id === job.id ? '1px solid var(--primary)' : '1px solid var(--border-color)',
                      cursor: 'pointer',
                      fontSize: '13px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: '600' }}>Score ≥{job.score_threshold} | {job.time_stop_days}d Stop</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {new Date(job.created_at).toLocaleTimeString()} - {job.id.slice(0, 8)}
                      </div>
                    </div>
                    <div>
                      <span className={`badge badge-${
                        job.status === 'COMPLETED' ? 'aplus' : job.status === 'FAILED' ? 'reject' : 'watch'
                      }`}>
                        {job.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Job details & logs */}
        <div className="glass-panel" style={{ padding: '28px' }}>
          {!activeJob ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
              <Clipboard size={48} style={{ marginBottom: '16px' }} />
              <h3>No Simulation Selected</h3>
              <p style={{ marginTop: '8px', fontSize: '14px' }}>Select a past run from history or execute a new configuration.</p>
            </div>
          ) : activeJob.status === 'RUNNING' || activeJob.status === 'PENDING' ? (
            <div className="loader-container">
              <div className="spinner"></div>
              <h3>Simulation in Progress</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Please wait, processing daily scans & simulating exits leg-by-leg...</p>
            </div>
          ) : activeJob.status === 'FAILED' ? (
            <div style={{ color: 'var(--danger)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px', fontWeight: '700', marginBottom: '16px' }}>
                <AlertTriangle /> Backtest Failed
              </div>
              <pre style={{
                background: 'rgba(244, 63, 94, 0.05)',
                border: '1px solid var(--danger)',
                padding: '16px',
                borderRadius: '8px',
                fontFamily: 'monospace',
                fontSize: '12px',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap'
              }}>
                {activeJob.error_message}
              </pre>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
                <div>
                  <h2 className="brand-name" style={{ fontSize: '22px' }}>Simulation Results</h2>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Capital: Rs. {activeJob.initial_capital.toLocaleString()} | Stop: {activeJob.time_stop_days} days
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className="badge badge-aplus" style={{ fontSize: '14px', padding: '6px 12px' }}>
                    Win Rate: {activeJob.metrics?.win_rate.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Performance Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '28px' }}>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>CAGR</div>
                  <div style={{ fontSize: '20px', fontWeight: '700', marginTop: '6px', color: activeJob.metrics?.cagr >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                    {activeJob.metrics?.cagr.toFixed(2)}%
                  </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Max Drawdown</div>
                  <div style={{ fontSize: '20px', fontWeight: '700', marginTop: '6px', color: 'var(--danger)' }}>
                    {activeJob.metrics?.max_drawdown.toFixed(2)}%
                  </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Sharpe Ratio</div>
                  <div style={{ fontSize: '20px', fontWeight: '700', marginTop: '6px', color: '#fff' }}>
                    {activeJob.metrics?.sharpe.toFixed(2)}
                  </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Expectancy</div>
                  <div style={{ fontSize: '20px', fontWeight: '700', marginTop: '6px', color: activeJob.metrics?.expectancy >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                    {activeJob.metrics?.expectancy.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Chart container */}
              <div style={{ marginBottom: '32px' }}>
                <h4 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '12px' }}>Equity Growth Curve</h4>
                <div id="equity-chart-container" style={{ height: '220px', width: '100%' }}></div>
              </div>

              {/* Trades list */}
              <div>
                <h4 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                  Execution Trade Ledger ({activeJob.metrics?.total_trades} Trades)
                </h4>
                {loadingTrades ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Loading trade ledger...</div>
                ) : activeJobTrades.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '12px 0' }}>
                    No trades executed (the strategy did not trigger any entries).
                  </div>
                ) : (
                  <div className="table-container" style={{ maxHeight: '240px', border: '1px solid var(--border-color)' }}>
                    <table className="table" style={{ fontSize: '13px' }}>
                      <thead>
                        <tr>
                          <th>Symbol</th>
                          <th>Entry Date</th>
                          <th>Exit Date</th>
                          <th>Entry Price</th>
                          <th>Exit Price</th>
                          <th>Qty</th>
                          <th>P&L</th>
                          <th>Exit Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeJobTrades.map((t) => (
                          <tr key={t.id}>
                            <td style={{ fontWeight: '700', color: '#fff' }}>{t.symbol}</td>
                            <td>{t.entry_date}</td>
                            <td>{t.exit_date || '-'}</td>
                            <td>{t.entry_price.toFixed(2)}</td>
                            <td>{t.exit_price ? t.exit_price.toFixed(2) : '-'}</td>
                            <td>{t.qty.toFixed(0)}</td>
                            <td style={{
                              fontWeight: '600',
                              color: t.pnl >= 0 ? 'var(--success)' : 'var(--danger)'
                            }}>
                              {t.pnl ? (t.pnl >= 0 ? '+' : '') + t.pnl.toFixed(2) : '-'}
                            </td>
                            <td>
                              <span className={`badge badge-${
                                t.reason === 'Target 2' || t.reason === 'Target 1' ? 'aplus' : t.reason === 'Stop Loss' ? 'reject' : 'watch'
                              }`} style={{ fontSize: '10px' }}>
                                {t.reason || '-'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
