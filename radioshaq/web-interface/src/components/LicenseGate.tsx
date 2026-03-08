import { Trans, useTranslation } from 'react-i18next';

type LicenseGateProps = {
  onAccept: () => void;
};

export function LicenseGate({ onAccept }: LicenseGateProps) {
  const { t } = useTranslation();
  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: '2rem',
        background: '#0b1220',
        color: '#e6edf3',
      }}
    >
      <section
        style={{
          maxWidth: 760,
          width: '100%',
          border: '1px solid #2f3b52',
          borderRadius: 12,
          padding: '1.5rem',
          background: '#111a2d',
        }}
      >
        <h1 style={{ marginTop: 0 }}>{t('license.title')}</h1>
        <p>
          <Trans i18nKey="license.intro" components={{ strong: <strong /> }} />
        </p>
        <p>
          {t('license.review')}{' '}
          <a
            href="https://github.com/josephrp/radioshaq/blob/main/LICENSE.md"
            target="_blank"
            rel="noreferrer"
            style={{ color: '#7ca5e0' }}
          >
            LICENSE.md
          </a>
          .
        </p>
        <button
          type="button"
          onClick={onAccept}
          style={{
            marginTop: '0.75rem',
            padding: '0.6rem 1rem',
            borderRadius: 8,
            border: '1px solid #4f6ea9',
            background: '#2053c9',
            color: '#fff',
            cursor: 'pointer',
          }}
        >
          {t('license.accept')}
        </button>
      </section>
    </main>
  );
}
