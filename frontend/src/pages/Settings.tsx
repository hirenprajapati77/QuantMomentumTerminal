import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import { 
  Lock, 
  Unlock, 
  Settings, 
  RefreshCw, 
  CheckCircle2, 
  AlertTriangle, 
  Eye, 
  EyeOff, 
  LogOut, 
  Clock, 
  ShieldAlert,
  ArrowRight
} from 'lucide-react';

interface Props {
  token: string | null;
  onUnlock: (token: string) => void;
  onLock: () => void;
}

export default function SettingsPage({ token, onUnlock, onLock }: Props) {
  const [pin, setPin] = useState<string>('');
  const [pinError, setPinError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  
  // Settings form state
  const [appId, setAppId] = useState<string>('');
  const [secretId, setSecretId] = useState<string>('');
  const [redirectUri, setRedirectUri] = useState<string>('');
  const [showSecret, setShowSecret] = useState<boolean>(false);
  
  // Settings info loaded from backend
  const [configInfo, setConfigInfo] = useState<any>({
    app_id_masked: 'Loading...',
    redirect_uri: 'Loading...',
    authenticated: false
  });
  
  const [saveStatus, setSaveStatus] = useState<{ success?: boolean; message?: string }>({});
  const [authUrlLoading, setAuthUrlLoading] = useState<boolean>(false);

  // Decode session token expiration
  const getExpiryTime = (tokenStr: string): number => {
    try {
      const decoded = atob(tokenStr);
      const parts = decoded.split(':');
      return parseInt(parts[0], 10) * 1000; // in ms
    } catch (e) {
      return 0;
    }
  };

  // Timer hook
  useEffect(() => {
    if (!token) return;
    
    const expiry = getExpiryTime(token);
    const updateTimer = () => {
      const left = Math.max(0, Math.floor((expiry - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left <= 0) {
        onLock();
      }
    };
    
    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [token, onLock]);

  // Load config hook
  useEffect(() => {
    if (!token) return;
    
    const fetchConfig = async () => {
      try {
        const data = await apiClient.get('/settings/fyers-config');
        setConfigInfo(data);
        setRedirectUri(data.redirect_uri || '');
      } catch (e: any) {
        if (e.message.includes('expired') || e.message.includes('token')) {
          onLock();
        } else {
          setSaveStatus({ success: false, message: e.message });
        }
      }
    };
    
    fetchConfig();
  }, [token, onLock]);

  const handlePinSubmit = async (enteredPin: string) => {
    if (enteredPin.length !== 4) return;
    
    setLoading(true);
    setPinError('');
    try {
      const data = await apiClient.post('/settings/unlock', { pin: enteredPin });
      apiClient.setToken(data.token);
      onUnlock(data.token);
      setPin('');
    } catch (e: any) {
      setPin('');
      setPinError(e.message || 'Invalid PIN');
    } finally {
      setLoading(false);
    }
  };

  const handleKeypadPress = (val: string) => {
    if (loading) return;
    
    if (val === 'C') {
      setPin('');
      setPinError('');
    } else if (val === 'B') {
      setPin(prev => prev.slice(0, -1));
    } else {
      if (pin.length < 4) {
        const newPin = pin + val;
        setPin(newPin);
        if (newPin.length === 4) {
          handlePinSubmit(newPin);
        }
      }
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!appId || !secretId || !redirectUri) {
      setSaveStatus({ success: false, message: 'All configuration fields are required.' });
      return;
    }
    
    setLoading(true);
    setSaveStatus({});
    try {
      const result = await apiClient.post('/settings/fyers-config', {
        app_id: appId,
        secret_id: secretId,
        redirect_uri: redirectUri
      });
      
      setSaveStatus({ success: true, message: result.message || 'Configuration saved successfully.' });
      
      // Reload masked view
      const updated = await apiClient.get('/settings/fyers-config');
      setConfigInfo(updated);
      
      // Clear password input fields for security hygiene
      setAppId('');
      setSecretId('');
    } catch (e: any) {
      setSaveStatus({ success: false, message: e.message || 'Failed to save configuration.' });
    } finally {
      setLoading(false);
    }
  };

  const handleReauthenticate = async () => {
    setAuthUrlLoading(true);
    setSaveStatus({});
    try {
      const data = await apiClient.get('/settings/login-url');
      if (data && data.login_url) {
        window.location.href = data.login_url;
      } else {
        throw new Error('No authentication URL returned from server.');
      }
    } catch (e: any) {
      setSaveStatus({ success: false, message: `Re-auth failed: ${e.message}` });
      setAuthUrlLoading(false);
    }
  };

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Locked UI: PIN entry keypad
  if (!token) {
    return (
      <div className="settings-lock-container">
        <div className="glass-panel lock-card">
          <div className="lock-icon-container">
            <Lock className="lock-icon" size={32} />
          </div>
          
          <h2 className="lock-title">Settings Gated</h2>
          <p className="lock-subtitle">Enter the 4-digit security PIN to access Fyers configuration.</p>
          
          {/* PIN Dots */}
          <div className="pin-dots">
            {[0, 1, 2, 3].map(i => (
              <div 
                key={i} 
                className={`pin-dot ${pin.length > i ? 'active' : ''} ${pinError ? 'error' : ''}`}
              />
            ))}
          </div>

          {pinError && (
            <div className="pin-error-message">
              <ShieldAlert size={16} />
              <span>{pinError}</span>
            </div>
          )}

          {/* Keypad */}
          <div className="pin-keypad">
            {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(val => (
              <button 
                key={val} 
                type="button"
                className="keypad-btn" 
                onClick={() => handleKeypadPress(val)}
                disabled={loading}
              >
                {val}
              </button>
            ))}
            <button 
              type="button"
              className="keypad-btn keypad-btn-action" 
              onClick={() => handleKeypadPress('C')}
              disabled={loading}
            >
              C
            </button>
            <button 
              type="button"
              className="keypad-btn" 
              onClick={() => handleKeypadPress('0')}
              disabled={loading}
            >
              0
            </button>
            <button 
              type="button"
              className="keypad-btn keypad-btn-action" 
              onClick={() => handleKeypadPress('B')}
              disabled={loading}
            >
              ⌫
            </button>
          </div>
          
          {loading && (
            <div className="unlock-loader">
              <RefreshCw className="spinner" size={16} />
              <span>Verifying PIN...</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Unlocked UI: Fyers configuration settings form
  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Settings style={{ color: 'var(--primary)' }} /> Broker Settings
          </h1>
          <p className="page-subtitle">Configure API client credentials, redirect parameters, and link session tokens.</p>
        </div>
        
        <div className="settings-session-widget glass-panel">
          <Clock size={16} style={{ color: 'var(--primary)' }} />
          <span>Session: <strong style={{ color: secondsLeft < 60 ? 'var(--danger)' : 'var(--success)' }}>{formatTime(secondsLeft)}</strong></span>
          <button 
            type="button" 
            className="session-lock-btn" 
            title="Lock Settings" 
            onClick={onLock}
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>

      <div className="settings-grid">
        {/* Connection Status Card */}
        <div className="glass-panel settings-card status-card">
          <h3 className="card-title">Fyers Authentication Status</h3>
          <div className="status-indicators">
            <div className="status-row">
              <span className="status-label">Current Masked App ID</span>
              <span className="status-value">{configInfo.app_id_masked}</span>
            </div>
            
            <div className="status-row">
              <span className="status-label">OAuth Redirect URL</span>
              <span className="status-value">{configInfo.redirect_uri}</span>
            </div>

            <div className="status-divider" />

            <div className="auth-status-badge-container">
              {configInfo.authenticated ? (
                <div className="auth-badge success">
                  <CheckCircle2 size={24} />
                  <div>
                    <h4>Authenticated</h4>
                    <p>Broker connection is active and valid.</p>
                  </div>
                </div>
              ) : (
                <div className="auth-badge warning">
                  <AlertTriangle size={24} />
                  <div>
                    <h4>Authentication Required</h4>
                    <p>Fyers access token is missing or expired.</p>
                  </div>
                </div>
              )}
            </div>

            <div className="auth-actions">
              <button
                type="button"
                className="btn btn-primary btn-full-width"
                onClick={handleReauthenticate}
                disabled={authUrlLoading}
              >
                {authUrlLoading ? (
                  <>
                    <RefreshCw className="spinner" size={16} />
                    Generating URL...
                  </>
                ) : (
                  <>
                    Re-authenticate Broker
                    <ArrowRight size={16} style={{ marginLeft: '8px' }} />
                  </>
                )}
              </button>
              <p className="auth-note">
                Re-authenticating redirects you to the Fyers broker login page. Ensure you save changes to your App ID and Secret below before authenticating.
              </p>
            </div>
          </div>
        </div>

        {/* Credentials Form Card */}
        <div className="glass-panel settings-card form-card">
          <h3 className="card-title">Update Fyers API Credentials</h3>
          <p className="card-description">
            Provide client credentials generated from your Fyers API dashboard. These settings will override environment defaults.
          </p>

          <form onSubmit={handleSaveConfig} className="settings-form">
            <div className="form-group">
              <label htmlFor="app-id">Fyers App ID</label>
              <input 
                id="app-id"
                type="text" 
                placeholder="Enter App ID (e.g. XAST342P8T-100)"
                value={appId}
                onChange={e => setAppId(e.target.value)}
                autoComplete="off"
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="secret-id">Fyers App Secret Key</label>
              <div className="password-input-wrapper">
                <input 
                  id="secret-id"
                  type={showSecret ? 'text' : 'password'} 
                  placeholder="Enter Secret Key (e.g. U5RHOQ1292)"
                  value={secretId}
                  onChange={e => setSecretId(e.target.value)}
                  autoComplete="off"
                  disabled={loading}
                />
                <button 
                  type="button" 
                  className="password-toggle-btn"
                  onClick={() => setShowSecret(!showSecret)}
                >
                  {showSecret ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="redirect-uri">Fyers Redirect URI</label>
              <input 
                id="redirect-uri"
                type="text" 
                placeholder="Enter Redirect URI"
                value={redirectUri}
                onChange={e => setRedirectUri(e.target.value)}
                autoComplete="off"
                disabled={loading}
              />
            </div>

            {saveStatus.message && (
              <div className={`form-feedback-alert ${saveStatus.success ? 'success' : 'error'}`}>
                {saveStatus.success ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                <span>{saveStatus.message}</span>
              </div>
            )}

            <button 
              type="submit" 
              className="btn btn-save" 
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw className="spinner" size={16} />
                  Saving Credentials...
                </>
              ) : (
                'Save Configuration'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
