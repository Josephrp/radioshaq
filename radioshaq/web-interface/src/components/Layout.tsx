import React from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { ApiStatus } from './ApiStatus';

const nav = [
  { to: '/', label: 'Audio' },
  { to: '/callsigns', label: 'Callsigns' },
  { to: '/messages', label: 'Messages' },
  { to: '/transcripts', label: 'Transcripts' },
  { to: '/radio', label: 'Radio' },
];

export function Layout() {
  const location = useLocation();
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{ borderBottom: '1px solid #ccc' }}>
        <nav style={{ padding: '0.5rem 1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <strong style={{ marginRight: '0.5rem' }}>RadioShaq</strong>
          {nav.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              style={{
                padding: '0.35rem 0.6rem',
                textDecoration: 'none',
                color: location.pathname === to ? '#0d47a1' : '#333',
                fontWeight: location.pathname === to ? 600 : 400,
                borderRadius: 4,
              }}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div style={{ padding: '0 1rem', borderTop: '1px solid #eee', background: '#fafafa' }}>
          <ApiStatus />
        </div>
      </header>
      <main style={{ padding: '1rem', maxWidth: 900, margin: '0 auto', width: '100%', flex: 1 }}>
        <Outlet />
      </main>
    </div>
  );
}
