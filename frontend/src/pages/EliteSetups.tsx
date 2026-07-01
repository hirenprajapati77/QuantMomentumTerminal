import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { formatDate } from '../utils/date';
import { Award, Zap } from 'lucide-react';

interface Props {
  onNavigate: (page: string, params?: any) => void;
}

export default function EliteSetups({ onNavigate }: Props) {
  const [setups, setSetups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchElite = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await apiClient.get('/scanner/results');
        // Filter by entry_triggered and grade = Elite or A+
        const filtered = data.filter((r: any) => 
          r.entry_triggered && (r.grade === 'Elite' || r.grade === 'A+')
        );
        setSetups(filtered);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchElite();
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Award style={{ color: 'var(--success)' }} /> Elite Setups
          </h1>
          <p className="page-subtitle">Verified entry triggers scoring ≥85 with simultaneous technical, volume, and sector alignment.</p>
        </div>
      </div>

      {loading ? (
        <div className="loader-container">
          <div className="spinner"></div>
          <span style={{ color: 'var(--text-secondary)' }}>Loading elite triggers...</span>
        </div>
      ) : error ? (
        <div className="glass-panel" style={{ padding: '24px', borderColor: 'var(--danger)', color: 'var(--danger)' }}>
          Error: {error}
        </div>
      ) : setups.length === 0 ? (
        <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          <Zap size={48} style={{ color: 'var(--text-muted)', marginBottom: '16px' }} />
          <h3>No Active Elite Signals</h3>
          <p style={{ marginTop: '8px', fontSize: '14px', maxWidth: '480px', marginInline: 'auto' }}>
            No high-conviction momentum breakouts met the strict 5-condition threshold in the recent scans.
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
                <th>Entry Status</th>
                <th>Entry Price</th>
                <th>Stop Loss</th>
                <th>Target 1</th>
                <th>Target 2</th>
                <th>Trailing Stop</th>
              </tr>
            </thead>
            <tbody>
              {setups.map((s, i) => (
                <tr
                  key={i}
                  className="clickable"
                  onClick={() => onNavigate('StockDetail', { symbol: s.symbol, date: s.date })}
                >
                  <td style={{ fontWeight: '700', color: 'var(--success)' }}>{s.symbol}</td>
                  <td>{formatDate(s.date)}</td>
                  <td>
                    <span className={`badge badge-${s.grade.toLowerCase().replace('+', 'plus')}`}>
                      {s.grade}
                    </span>
                  </td>
                  <td style={{ fontWeight: '600' }}>{s.final_score.toFixed(1)}</td>
                  <td>
                    <span className={`badge badge-status-${(s.entry_status || 'pending').toLowerCase().replace(' ', '-')}`}>
                      {s.entry_status || 'Pending'}
                    </span>
                  </td>
                  <td style={{ fontWeight: '600', color: 'var(--success)' }}>
                    {s.entry ? '₹' + s.entry.toFixed(2) : '-'}
                  </td>
                  <td style={{ color: 'var(--danger)' }}>
                    {s.stop ? '₹' + s.stop.toFixed(2) : '-'}
                  </td>
                  <td style={{ color: 'var(--success)', fontWeight: '500' }}>
                    {s.target1 ? '₹' + s.target1.toFixed(2) : '-'}
                  </td>
                  <td style={{ color: '#38bdf8', fontWeight: '500' }}>
                    {s.target2 ? '₹' + s.target2.toFixed(2) : '-'}
                  </td>
                  <td style={{ color: 'var(--warning)', fontWeight: '500' }}>
                    {s.target3 ? '₹' + s.target3.toFixed(2) : '-'}
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
