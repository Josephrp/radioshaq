import React, { useCallback, useEffect, useState } from 'react';
import { getApiBase, getHealth, getMe, getRadioStatus, getToken, setApiToken } from '../services/radioshaqApi';

const HEALTH_POLL_MS = 6000;
const AUTH_POLL_MS = 10000;
const RADIO_POLL_MS = 8000;

export function ApiStatus() {
  const [apiLive, setApiLive] = useState<boolean | null>(null);
  const [authUser, setAuthUser] = useState<string | null>(null);
  const [radioConnected, setRadioConnected] = useState<boolean | null>(null);
  const [radioDetail, setRadioDetail] = useState<string | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [loginSubject, setLoginSubject] = useState('dashboard');
  const [loginRole, setLoginRole] = useState('field');
  const [loginStationId, setLoginStationId] = useState('');
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      await getHealth();
      setApiLive(true);
    } catch {
      setApiLive(false);
    }
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      const me = await getMe();
      setAuthUser(me.sub ?? 'ok');
    } catch {
      setAuthUser(null);
    }
  }, []);

  const checkRadio = useCallback(async () => {
    if (!apiLive || !authUser) {
      setRadioConnected(null);
      setRadioDetail(null);
      return;
    }
    try {
      const status = await getRadioStatus();
      setRadioConnected(status.connected);
      if (status.connected && (status.frequency_hz != null || status.mode)) {
        const parts = [];
        if (status.frequency_hz != null) parts.push(`${(status.frequency_hz / 1e6).toFixed(3)} MHz`);
        if (status.mode) parts.push(status.mode);
        if (status.ptt) parts.push('TX');
        setRadioDetail(parts.length ? parts.join(' ') : null);
      } else {
        setRadioDetail(status.reason ?? null);
      }
    } catch {
      setRadioConnected(null);
      setRadioDetail(null);
    }
  }, [apiLive, authUser]);

  useEffect(() => {
    checkHealth();
    const t = setInterval(checkHealth, HEALTH_POLL_MS);
    return () => clearInterval(t);
  }, [checkHealth]);

  useEffect(() => {
    checkAuth();
    const t = setInterval(checkAuth, AUTH_POLL_MS);
    return () => clearInterval(t);
  }, [checkAuth]);

  useEffect(() => {
    checkRadio();
    const t = setInterval(checkRadio, RADIO_POLL_MS);
    return () => clearInterval(t);
  }, [checkRadio]);

  const handleGetToken = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginBusy(true);
    setLoginError(null);
    try {
      const res = await getToken({
        subject: loginSubject.trim() || 'dashboard',
        role: loginRole,
        station_id: loginStationId.trim() || undefined,
      });
      setApiToken(res.access_token);
      await checkAuth();
      setShowLogin(false);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Failed to get token');
    } finally {
      setLoginBusy(false);
    }
  };

  const handleLogout = () => {
    setApiToken(null);
    setAuthUser(null);
  };

  const apiBase = getApiBase();

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: '0.75rem',
        fontSize: '0.85rem',
        padding: '0.35rem 0',
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.35rem',
        }}
        title={apiBase}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: apiLive === true ? '#2e7d32' : apiLive === false ? '#c62828' : '#9e9e9e',
          }}
          aria-hidden
        />
        <span>API: {apiLive === true ? 'live' : apiLive === false ? 'disconnected' : '…'}</span>
      </span>
      <span style={{ color: '#666' }}>|</span>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.35rem',
        }}
        title={radioDetail ?? undefined}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background:
              radioConnected === true ? '#1565c0' : radioConnected === false ? '#9e9e9e' : 'transparent',
            border: radioConnected === null ? '1px solid #9e9e9e' : 'none',
          }}
          aria-hidden
        />
        <span>
          Radio: {radioConnected === true ? 'connected' : radioConnected === false ? 'not connected' : '—'}
          {radioDetail && radioConnected === true && (
            <span style={{ marginLeft: '0.25rem', color: '#555' }}>({radioDetail})</span>
          )}
        </span>
      </span>
      <span style={{ color: '#666' }}>|</span>
      <span>
        Auth: {authUser ? (
          <>
            <strong>{authUser}</strong>
            <button
              type="button"
              onClick={handleLogout}
              style={{ marginLeft: '0.35rem', fontSize: '0.75rem', padding: '0.1rem 0.35rem' }}
            >
              Logout
            </button>
          </>
        ) : (
          <>
            —
            {!showLogin ? (
              <button
                type="button"
                onClick={() => setShowLogin(true)}
                style={{ marginLeft: '0.35rem', fontSize: '0.75rem', padding: '0.1rem 0.35rem' }}
              >
                Get token
              </button>
            ) : null}
          </>
        )}
      </span>
      {showLogin && (
        <form
          onSubmit={handleGetToken}
          style={{
            display: 'inline-flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '0.35rem',
            marginLeft: '0.5rem',
          }}
        >
          <input
            type="text"
            value={loginSubject}
            onChange={(e) => setLoginSubject(e.target.value)}
            placeholder="Subject"
            size={10}
            style={{ padding: '0.2rem 0.4rem' }}
            aria-label="Token subject"
          />
          <select
            value={loginRole}
            onChange={(e) => setLoginRole(e.target.value)}
            style={{ padding: '0.2rem 0.4rem' }}
            aria-label="Role"
          >
            <option value="field">field</option>
            <option value="hq">hq</option>
            <option value="receiver">receiver</option>
          </select>
          <input
            type="text"
            value={loginStationId}
            onChange={(e) => setLoginStationId(e.target.value)}
            placeholder="Station ID"
            size={12}
            style={{ padding: '0.2rem 0.4rem' }}
            aria-label="Station ID (optional)"
          />
          <button type="submit" disabled={loginBusy}>
            {loginBusy ? '…' : 'Get token'}
          </button>
          <button type="button" onClick={() => { setShowLogin(false); setLoginError(null); }}>
            Cancel
          </button>
          {loginError && <span style={{ color: '#c62828', fontSize: '0.8rem' }}>{loginError}</span>}
        </form>
      )}
    </div>
  );
}
