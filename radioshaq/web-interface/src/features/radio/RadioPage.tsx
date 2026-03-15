import React, { useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { listBands, sendTts } from '../../services/radioshaqApi';

export function RadioPage() {
  const { t } = useTranslation();
  const [bands, setBands] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ttsMessage, setTtsMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadBands = () => {
    listBands()
      .then((res) => setBands(res.bands ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : t('common.failedToLoad')))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadBands();
  }, []);

  // Live polling: refresh bands every 60s
  useEffect(() => {
    const interval = setInterval(loadBands, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleSendTts = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ttsMessage.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await sendTts({ message: ttsMessage.trim() });
      setTtsMessage('');
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="radio-page">
      <h1>{t('radio.title')}</h1>
      {error && <p role="alert" style={{ color: 'crimson' }}>{error}</p>}

      <section style={{ marginBottom: '1.5rem' }}>
        <h2>{t('radio.bands')}</h2>
        <p style={{ marginTop: 0 }}>
          {loading ? <span>{t('common.loading')}</span> : <span>{bands.length ? bands.join(', ') : t('radio.none')}</span>}
          <button type="button" onClick={loadBands} disabled={loading} style={{ marginLeft: '0.5rem' }}>
            {t('common.refresh')}
          </button>
          <span style={{ marginLeft: '0.5rem', color: '#666', fontSize: '0.85rem' }}>{t('radio.autoRefresh60')}</span>
        </p>
      </section>

      <section>
        <h2>{t('radio.sendTtsSection')}</h2>
        <p style={{ fontSize: '0.9rem', color: '#555' }}>{t('radio.ttsDescription')}</p>
        <form onSubmit={handleSendTts} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={ttsMessage}
            onChange={(e) => setTtsMessage(e.target.value)}
            placeholder={t('radio.messageToSpeakPlaceholder')}
            style={{ padding: '0.4rem', minWidth: 200, flex: 1 }}
            aria-label={t('messages.message')}
          />
          <button type="submit" disabled={submitting || !ttsMessage.trim()}>
            {submitting ? t('messages.sending') : t('radio.sendTts')}
          </button>
        </form>
      </section>

      <p style={{ marginTop: '1.5rem', fontSize: '0.9rem', color: '#555' }}>
        <Trans i18nKey="radio.relayHint" components={{ strong: <strong /> }} />
      </p>
    </div>
  );
}
