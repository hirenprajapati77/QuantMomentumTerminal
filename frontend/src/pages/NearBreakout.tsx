import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { formatDate } from '../utils/date';
import { Eye, TrendingUp } from 'lucide-react';

interface Props {
  onNavigate: (page: string, params?: any) => void;
}

export default function NearBreakout({ onNavigate }: Props) {
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchWatchlist = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await apiClient.get('/scanner/results');
        // Filter by grade = Watch (which is score 70-79) or score in [70, 84] (Watch & A grade but no entry trigger)
        const filtered = data.filter((r: any) => 
          r.grade === 'Watch' || (r.grade === 'A' && !r.entry_triggered)
        );
        setWatchlist(filtered);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchWatchlist();
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Eye style={{ color: 'var(--warning)' }} /> Near Breakout (Watchlist)
          </h1>
          <p className="page-subtitle">Consolidating setups with high composite scores (70–84) currently building momentum.</p>
        </div>
      </div>

      {loading ? (
        <div className="loader-container">
          <div className="spinner"></div>
          <span style={{ color: 'var(--text-secondary)' }}>Loading watchlist...</span>
        </div>
      ) : error ? (
        <div className="glass-panel" style={{ padding: '24px', borderColor: 'var(--danger)', color: 'var(--danger)' }}>
          Error: {error}
        </div>
      ) : watchlist.length === 0 ? (
        <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          <TrendingUp size={48} style={{ color: 'var(--text-muted)', marginBottom: '16px' }} />
          <h3>Watchlist Empty</h3>
          <p style={{ marginTop: '8px', fontSize: '14px', maxWidth: '480px', marginInline: 'auto' }}>
            No stocks are currently classified under the Watchlist/Near-Breakout score threshold.
          </p>
        </div>
      ) : (
        <div className="glass-panel table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Date</th>
                <th>Grade</th>
                <th>Score</th>
                <th>Tech Score</th>
                <th>Fund Score</th>
                <th>Vol Ratio</th>
                <th>Close %</th>
                <th>Fund Gate Pass</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map((w, i) => (
                <tr
                  key={i}
                  className="clickable"
                  onClick={() => onNavigate('StockDetail', { symbol: w.symbol, date: w.date })}
                >
                  <td style={{ fontWeight: '700', color: 'var(--warning)' }}>{w.symbol}</td>
                  <td>{formatDate(w.date)}</td>
                  <td>
                    <span className="badge badge-watch">
                      {w.grade}
                    </span>
                  </td>
                  <td style={{ fontWeight: '600' }}>{w.final_score.toFixed(1)}</td>
                  <td>{w.technical_score.toFixed(1)}</td>
                  <td>{w.fundamental_score.toFixed(1)}</td>
                  <td>{w.breakout_vol_ratio ? w.breakout_vol_ratio.toFixed(2) + 'x' : '-'}</td>
                  <td>{w.close_pct_of_range ? (w.close_pct_of_range * 100).toFixed(0) + '%' : '-'}</td>
                  <td>
                    <span className={`badge badge-trigger-${w.passes_fundamental ? 'yes' : 'no'}`}>
                      {w.passes_fundamental ? 'PASSED' : 'FAILED'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
