import { Link, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ApiStatus } from './ApiStatus';
import { SUPPORTED_LANGUAGES, type SupportedLanguageCode } from '../i18n';

const navPaths = [
  { to: '/', key: 'audio' as const },
  { to: '/callsigns', key: 'callsigns' as const },
  { to: '/messages', key: 'messages' as const },
  { to: '/transcripts', key: 'transcripts' as const },
  { to: '/radio', key: 'radio' as const },
  { to: '/settings', key: 'settings' as const },
];

export function Layout() {
  const location = useLocation();
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language as SupportedLanguageCode;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{ borderBottom: '1px solid #ccc' }}>
        <nav style={{ padding: '0.5rem 1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <strong style={{ marginRight: '0.5rem' }}>{t('nav.appName')}</strong>
          {navPaths.map(({ to, key }) => (
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
              {t(`nav.${key}`)}
            </Link>
          ))}
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.9rem', color: '#666' }}>{t('nav.language')}:</span>
            <select
              value={currentLang}
              onChange={(e) => i18n.changeLanguage(e.target.value as SupportedLanguageCode)}
              style={{ padding: '0.25rem 0.5rem', borderRadius: 4, border: '1px solid #ccc' }}
              aria-label={t('nav.language')}
            >
              {SUPPORTED_LANGUAGES.map(({ code, label }) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </span>
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
