import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { ArrowLeft, Award, ShieldCheck, TrendingUp, HelpCircle } from 'lucide-react';

interface Props {
  symbol: string;
  triggerDate?: string;
  onBack: () => void;
}

export default function StockDetail({ symbol, triggerDate, onBack }: Props) {
  const [candles, setCandles] = useState<any[]>([]);
  const [scanResult, setScanResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadDetails = async () => {
      setLoading(true);
      setError('');
      try {
        // Load candles (last 120 candles)
        const candleData = await apiClient.get(`/scanner/candles?symbol=${symbol}&limit=120`);
        setCandles(candleData);

        // Load scan results to find the metadata
        const results = await apiClient.get(`/scanner/results?symbol=${symbol}`);
        if (results && results.length > 0) {
          // Find matching date result, or just use the latest one
          const match = triggerDate 
            ? results.find((r: any) => r.date === triggerDate)
            : results[0];
          setScanResult(match || results[0]);
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    loadDetails();
  }, [symbol, triggerDate]);

  useEffect(() => {
    let timer: any = null;
    if (candles.length > 0 && !loading) {
      timer = setTimeout(() => {
        plotCandlestickChart();
      }, 50);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [candles, scanResult, loading]);

  const plotCandlestickChart = () => {
    const dates = candles.map(c => c.date);
    const opens = candles.map(c => c.open);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    const closes = candles.map(c => c.close);

    const traceCandle = {
      x: dates,
      open: opens,
      high: highs,
      low: lows,
      close: closes,
      type: 'candlestick',
      xaxis: 'x',
      yaxis: 'y',
      name: symbol,
      increasing: { line: { color: '#10b981' } },
      decreasing: { line: { color: '#f43f5e' } }
    };

    const data: any[] = [traceCandle];
    const shapes: any[] = [];

    // If we have a scan result, draw entry, stop, and target levels
    if (scanResult) {
      const dateStr = scanResult.date.substring(0, 10);
      const triggerCandle = candles.find(c => c.date.substring(0, 10) === dateStr);
      
      const entryPrice = scanResult.entry || (triggerCandle ? triggerCandle.close : closes[closes.length - 1]);
      const stopLoss = scanResult.stop || entryPrice * 0.94;
      const target1 = scanResult.target1 || entryPrice * 1.10;
      const target2 = scanResult.target2 || entryPrice * 1.20;
      const target3 = scanResult.target3; // dynamic trailing stop from API

      // Add horizontal line shapes for clean visualization
      const addLineShape = (price: number, color: string, label: string) => {
        shapes.push({
          type: 'line',
          xref: 'x',
          yref: 'y',
          x0: dates[0],
          y0: price,
          x1: dates[dates.length - 1],
          y1: price,
          line: {
            color: color,
            width: 1.5,
            dash: 'dash'
          }
        });
      };

      addLineShape(entryPrice, '#e2e8f0', 'Entry Level');
      addLineShape(stopLoss, '#f43f5e', 'Stop Loss');
      addLineShape(target1, '#10b981', 'Target 1');
      addLineShape(target2, '#38bdf8', 'Target 2');
      
      if (target3) {
        addLineShape(target3, '#fbbf24', 'Trailing Stop');
      }
    }

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
        linecolor: 'rgba(255, 255, 255, 0.08)',
        rangeslider: { visible: false }
      },
      yaxis: {
        gridcolor: 'rgba(255, 255, 255, 0.04)',
        linecolor: 'rgba(255, 255, 255, 0.08)',
        autorange: true,
        fixedrange: false
      },
      shapes: shapes
    };

    const config = {
      responsive: true,
      displayModeBar: false
    };

    const Plotly = (window as any).Plotly;
    if (Plotly) {
      Plotly.newPlot('candlestick-chart-container', data, layout, config);
    }
  };

  // Compute fallback values for render using scanResult's date-specific close price
  let entryPrice = 0;
  let stopLoss = 0;
  let target1 = 0;
  let target2 = 0;
  
  if (scanResult && candles.length > 0) {
    const dateStr = scanResult.date.substring(0, 10);
    const triggerCandle = candles.find(c => c.date.substring(0, 10) === dateStr);
    const fallbackBasePrice = triggerCandle ? triggerCandle.close : candles[candles.length - 1].close;
    entryPrice = scanResult.entry || fallbackBasePrice;
    stopLoss = scanResult.stop || entryPrice * 0.94;
    target1 = scanResult.target1 || entryPrice * 1.10;
    target2 = scanResult.target2 || entryPrice * 1.20;
  }

  return (
    <div>
      <div className="page-header">
        <button className="btn btn-secondary" onClick={onBack} style={{ gap: '6px' }}>
          <ArrowLeft size={16} /> Back
        </button>
        <div>
          <h1 className="page-title">{symbol} Analysis</h1>
          <p className="page-subtitle">Historical price action, indicators, and composite scorecard.</p>
        </div>
      </div>

      {loading ? (
        <div className="loader-container">
          <div className="spinner"></div>
          <span style={{ color: 'var(--text-secondary)' }}>Loading stock profile...</span>
        </div>
      ) : error ? (
        <div className="glass-panel" style={{ padding: '24px', borderColor: 'var(--danger)', color: 'var(--danger)' }}>
          Error: {error}
        </div>
      ) : (
        <div className="detail-layout">
          {/* Chart Panel */}
          <div className="glass-panel chart-card">
            <h3 className="brand-name" style={{ fontSize: '18px', marginBottom: '16px' }}>Interactive Candlestick</h3>
            <div id="candlestick-chart-container" style={{ height: '380px', width: '100%' }}></div>
            {scanResult && (
              <div style={{ display: 'flex', gap: '15px', marginTop: '16px', fontSize: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ display: 'inline-block', width: '12px', height: '2px', backgroundColor: '#e2e8f0', borderStyle: 'dashed' }}></span>
                  Entry (₹{entryPrice.toFixed(2)}) [{scanResult.entry_status || '—'}]
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ display: 'inline-block', width: '12px', height: '2px', backgroundColor: '#10b981', borderStyle: 'dashed' }}></span>
                  Target 1 (₹{target1.toFixed(2)})
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ display: 'inline-block', width: '12px', height: '2px', backgroundColor: '#38bdf8', borderStyle: 'dashed' }}></span>
                  Target 2 (₹{target2.toFixed(2)})
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ display: 'inline-block', width: '12px', height: '2px', backgroundColor: '#f43f5e', borderStyle: 'dashed' }}></span>
                  Stop Loss (₹{stopLoss.toFixed(2)})
                </span>
                {scanResult.target3 && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ display: 'inline-block', width: '12px', height: '2px', backgroundColor: '#fbbf24', borderStyle: 'dashed' }}></span>
                    Trailing Stop (₹{scanResult.target3.toFixed(2)})
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Metadata Panel */}
          <div className="metrics-panel">
            {scanResult && (
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 className="brand-name" style={{ fontSize: '18px', marginBottom: '20px' }}>Strategy Scorecard</h3>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>COMPOSITE GRADE</span>
                    <div style={{ fontSize: '32px', fontWeight: '800', fontFamily: 'var(--font-display)', color: 'var(--primary)' }}>
                      {scanResult.grade}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>FINAL SCORE</span>
                    <div style={{ fontSize: '32px', fontWeight: '800', fontFamily: 'var(--font-display)' }}>
                      {scanResult.final_score.toFixed(1)} / 100
                    </div>
                  </div>
                </div>

                {scanResult.remarks && (
                  <div style={{ marginBottom: '20px', padding: '12px', borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.02)', borderLeft: '3px solid var(--primary)', fontSize: '13px', color: 'var(--text-secondary)' }}>
                    <strong>Remarks:</strong> {scanResult.remarks}
                  </div>
                )}

                <div className="metric-section-title">Trade Info</div>
                <div className="metric-row">
                  <span className="metric-label">Sector</span>
                  <span className="metric-value">{scanResult.sector || 'Unknown'}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Confidence</span>
                  <span className="metric-value">
                    <span className={`badge badge-conf-${(scanResult.confidence || 'low').toLowerCase()}`}>
                      {scanResult.confidence || 'Low'}
                    </span>
                  </span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Holding Window</span>
                  <span className="metric-value">{scanResult.holding_days !== undefined ? scanResult.holding_days + ' Trading Days' : '-'}</span>
                </div>

                <div className="metric-section-title">Technical breakdown</div>
                <div className="metric-row">
                  <span className="metric-label">Technical Score</span>
                  <span className="metric-value">{scanResult.technical_score.toFixed(1)}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Volume Expansion Ratio</span>
                  <span className="metric-value">{scanResult.breakout_vol_ratio ? scanResult.breakout_vol_ratio.toFixed(2) + 'x' : '-'}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Candle Close % of Range</span>
                  <span className="metric-value">{scanResult.close_pct_of_range ? (scanResult.close_pct_of_range * 100).toFixed(0) + '%' : '-'}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Upper Wick % of Range</span>
                  <span className="metric-value">{scanResult.upper_wick_pct ? (scanResult.upper_wick_pct * 100).toFixed(0) + '%' : '-'}</span>
                </div>

                <div className="metric-section-title" style={{ marginTop: '20px' }}>Fundamental Filters</div>
                <div className="metric-row">
                  <span className="metric-label">Fundamental Score</span>
                  <span className="metric-value">{scanResult.fundamental_score.toFixed(1)}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Fundamental Gate status</span>
                  <span className="metric-value" style={{ color: scanResult.passes_fundamental ? 'var(--success)' : 'var(--danger)' }}>
                    {scanResult.passes_fundamental ? 'PASSED' : 'FAILED (Capped)'}
                  </span>
                </div>
              </div>
            )}

            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 className="brand-name" style={{ fontSize: '18px', marginBottom: '16px' }}>Breakout Criteria</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Trend (50/150/200 DMA)</span>
                  <span style={{ color: 'var(--success)' }}>Confirmed</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>VCP Contraction Leg</span>
                  <span style={{ color: 'var(--success)' }}>Valid</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Volume Expansion (&gt;2.0x)</span>
                  <span style={{ color: scanResult?.breakout_vol_ratio >= 2.0 ? 'var(--success)' : 'var(--text-muted)' }}>
                    {scanResult?.breakout_vol_ratio ? scanResult.breakout_vol_ratio.toFixed(2) + 'x' : 'Pending'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
