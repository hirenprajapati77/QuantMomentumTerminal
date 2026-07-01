import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { formatDate } from '../utils/date';
import { Search, Filter, Loader } from 'lucide-react';

interface Props {
  onNavigate: (page: string, params?: any) => void;
}

export default function Scanner({ onNavigate }: Props) {
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Filters
  const [search, setSearch] = useState('');
  const [gradeFilter, setGradeFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');

  const fetchResults = async () => {
    setLoading(true);
    setError('');
    try {
      let query = '';
      const params = [];
      if (dateFilter) params.push(`start_date=${dateFilter}&end_date=${dateFilter}`);
      if (gradeFilter) params.push(`grade=${gradeFilter}`);
      if (params.length > 0) {
        query = '?' + params.join('&');
      }
      
      const data = await apiClient.get(`/scanner/results${query}`);
      setResults(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, [gradeFilter, dateFilter]);

  const filteredResults = results.filter(r => 
    r.symbol.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Momentum Scanner</h1>
          <p className="page-subtitle">Composite scores, entry signals, and breakdown factors for filtered universe.</p>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px' }}>
        <div className="filters-bar">
          <div className="form-group" style={{ margin: 0, minWidth: '220px' }}>
            <label className="form-label">Search Symbol</label>
            <div style={{ position: 'relative' }}>
              <Search size={16} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="RELIANCE, TCS..."
                className="form-input"
                style={{ paddingLeft: '40px', width: '100%' }}
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group" style={{ margin: 0, minWidth: '160px' }}>
            <label className="form-label">Grade</label>
            <select
              className="form-input"
              value={gradeFilter}
              onChange={e => setGradeFilter(e.target.value)}
            >
              <option value="">All Grades</option>
              <option value="Elite">Elite (90-100)</option>
              <option value="A+">A+ (85-89)</option>
              <option value="A">A (80-84)</option>
              <option value="Watch">Watch (70-79)</option>
              <option value="Reject">Reject (&lt;70)</option>
            </select>
          </div>

          <div className="form-group" style={{ margin: 0, minWidth: '180px' }}>
            <label className="form-label">Date</label>
            <input
              type="date"
              className="form-input"
              value={dateFilter}
              onChange={e => setDateFilter(e.target.value)}
            />
          </div>

          <button
            className="btn btn-secondary"
            style={{ marginTop: '22px' }}
            onClick={() => {
              setSearch('');
              setGradeFilter('');
              setDateFilter('');
            }}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loader-container">
          <div className="spinner"></div>
          <span style={{ color: 'var(--text-secondary)' }}>Loading scan logs...</span>
        </div>
      ) : error ? (
        <div className="glass-panel" style={{ padding: '24px', borderColor: 'var(--danger)', color: 'var(--danger)' }}>
          Error: {error}
        </div>
      ) : filteredResults.length === 0 ? (
        <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          No scan results match the current filters.
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
                <th>Confidence</th>
                <th>Entry Status</th>
                <th>Entry Price</th>
                <th>Stop Loss</th>
                <th>Target 1</th>
                <th>Vol Ratio</th>
                <th>Close %</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((r, i) => (
                <tr
                  key={i}
                  className="clickable"
                  onClick={() => onNavigate('StockDetail', { symbol: r.symbol, date: r.date })}
                >
                  <td style={{ fontWeight: '700', color: 'var(--primary)' }}>{r.symbol}</td>
                  <td>{formatDate(r.date)}</td>
                  <td>
                    <span className={`badge badge-${r.grade.toLowerCase().replace('+', 'plus')}`}>
                      {r.grade}
                    </span>
                  </td>
                  <td style={{ fontWeight: '600' }}>{r.final_score.toFixed(1)}</td>
                  <td>
                    <span className={`badge badge-conf-${(r.confidence || 'low').toLowerCase()}`}>
                      {r.confidence || 'Low'}
                    </span>
                  </td>
                  <td>
                    <span className={`badge badge-status-${(r.entry_status || 'pending').toLowerCase().replace(' ', '-')}`}>
                      {r.entry_status || 'Pending'}
                    </span>
                  </td>
                  <td style={{ fontWeight: '600', color: 'var(--success)' }}>
                    {r.entry ? '₹' + r.entry.toFixed(2) : '-'}
                  </td>
                  <td style={{ color: 'var(--danger)' }}>
                    {r.stop ? '₹' + r.stop.toFixed(2) : '-'}
                  </td>
                  <td style={{ color: '#38bdf8' }}>
                    {r.target1 ? '₹' + r.target1.toFixed(2) : '-'}
                  </td>
                  <td>{r.breakout_vol_ratio ? r.breakout_vol_ratio.toFixed(1) + 'x' : '-'}</td>
                  <td>{r.close_pct_of_range ? (r.close_pct_of_range * 100).toFixed(0) + '%' : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
