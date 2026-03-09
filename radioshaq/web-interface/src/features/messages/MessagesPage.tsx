import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { processMessage, whitelistRequest, injectMessage, injectAndStore, relayMessage } from '../../services/radioshaqApi';

type Tab = 'process' | 'whitelist' | 'inject' | 'inject_store' | 'relay';

export function MessagesPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('process');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Process
  const [processText, setProcessText] = useState('');
  // Whitelist
  const [whitelistText, setWhitelistText] = useState('');
  const [whitelistCallsign, setWhitelistCallsign] = useState('');
  // Inject
  const [injectText, setInjectText] = useState('');
  const [injectBand, setInjectBand] = useState('');
  const [injectSource, setInjectSource] = useState('');
  const [injectDest, setInjectDest] = useState('');
  // Inject and store (whitelist enforced)
  const [storeText, setStoreText] = useState('');
  const [storeBand, setStoreBand] = useState('');
  const [storeSource, setStoreSource] = useState('');
  const [storeDest, setStoreDest] = useState('');
  // Relay
  const [relayMessageText, setRelayMessageText] = useState('');
  const [relaySourceBand, setRelaySourceBand] = useState('40m');
  const [relayTargetBand, setRelayTargetBand] = useState('2m');
  const [relaySourceCs, setRelaySourceCs] = useState('UNKNOWN');
  const [relayDestCs, setRelayDestCs] = useState('');

  const runProcess = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!processText.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await processMessage({ message: processText.trim() });
      setResult(JSON.stringify({ success: res.success, message: res.message, task_id: res.task_id }, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const runWhitelist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!whitelistText.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await whitelistRequest({
        text: whitelistText.trim(),
        callsign: whitelistCallsign.trim() || undefined,
        send_audio_back: false,
      });
      setResult(JSON.stringify({ success: res.success, message: res.message, approved: res.approved }, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const runInject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!injectText.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await injectMessage({
        text: injectText.trim(),
        band: injectBand.trim() || undefined,
        source_callsign: injectSource.trim() || undefined,
        destination_callsign: injectDest.trim() || undefined,
      });
      setResult(JSON.stringify(res, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const runInjectAndStore = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!storeText.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await injectAndStore({
        text: storeText.trim(),
        band: storeBand.trim() || undefined,
        source_callsign: storeSource.trim() || undefined,
        destination_callsign: storeDest.trim() || undefined,
      });
      setResult(JSON.stringify(res, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const runRelay = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!relayMessageText.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await relayMessage({
        message: relayMessageText.trim(),
        source_band: relaySourceBand,
        target_band: relayTargetBand,
        source_callsign: relaySourceCs || 'UNKNOWN',
        destination_callsign: relayDestCs.trim() || undefined,
      });
      setResult(JSON.stringify(res, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const tabs: { key: Tab; labelKey: string }[] = [
    { key: 'process', labelKey: 'messages.process' },
    { key: 'whitelist', labelKey: 'messages.whitelist' },
    { key: 'inject', labelKey: 'messages.inject' },
    { key: 'inject_store', labelKey: 'messages.injectStore' },
    { key: 'relay', labelKey: 'messages.relay' },
  ];

  return (
    <div className="messages-page">
      <h1>{t('messages.title')}</h1>
      {error && <p role="alert" style={{ color: 'crimson' }}>{error}</p>}
      {result && <pre style={{ background: '#f5f5f5', padding: '0.75rem', overflow: 'auto', fontSize: '0.9rem' }}>{result}</pre>}

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {tabs.map(({ key, labelKey }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            style={{ fontWeight: tab === key ? 600 : 400, padding: '0.4rem 0.75rem' }}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>

      {tab === 'process' && (
        <form onSubmit={runProcess}>
          <h2>{t('messages.process')}</h2>
          <textarea
            value={processText}
            onChange={(e) => setProcessText(e.target.value)}
            placeholder={t('messages.processPlaceholder')}
            rows={3}
            style={{ width: '100%', maxWidth: 400, padding: '0.5rem', marginBottom: '0.5rem' }}
          />
          <button type="submit" disabled={submitting || !processText.trim()}>{submitting ? t('messages.sending') : t('messages.send')}</button>
        </form>
      )}

      {tab === 'whitelist' && (
        <form onSubmit={runWhitelist}>
          <h2>{t('messages.whitelist')}</h2>
          <textarea
            value={whitelistText}
            onChange={(e) => setWhitelistText(e.target.value)}
            placeholder={t('messages.requestPlaceholder')}
            rows={3}
            style={{ width: '100%', maxWidth: 400, padding: '0.5rem', marginBottom: '0.5rem' }}
          />
          <input
            type="text"
            value={whitelistCallsign}
            onChange={(e) => setWhitelistCallsign(e.target.value)}
            placeholder={t('messages.callsignOptional')}
            maxLength={10}
            style={{ display: 'block', marginBottom: '0.5rem', padding: '0.4rem', width: 120 }}
          />
          <button type="submit" disabled={submitting || !whitelistText.trim()}>{submitting ? t('messages.sending') : t('messages.send')}</button>
        </form>
      )}

      {tab === 'inject' && (
        <form onSubmit={runInject}>
          <h2>Inject message (demo RX path)</h2>
          <textarea
            value={injectText}
            onChange={(e) => setInjectText(e.target.value)}
            placeholder="Message text to inject…"
            rows={2}
            style={{ width: '100%', maxWidth: 400, padding: '0.5rem', marginBottom: '0.5rem' }}
          />
          <input type="text" value={injectBand} onChange={(e) => setInjectBand(e.target.value)} placeholder="Band (e.g. 40m)" style={{ marginRight: '0.5rem', padding: '0.4rem', width: 80 }} />
          <input type="text" value={injectSource} onChange={(e) => setInjectSource(e.target.value)} placeholder="Source callsign" style={{ marginRight: '0.5rem', padding: '0.4rem', width: 100 }} />
          <input type="text" value={injectDest} onChange={(e) => setInjectDest(e.target.value)} placeholder="Destination callsign" style={{ marginRight: '0.5rem', padding: '0.4rem', width: 100 }} />
          <br />
          <button type="submit" disabled={submitting || !injectText.trim()} style={{ marginTop: '0.5rem' }}>{submitting ? 'Injecting…' : 'Inject'}</button>
        </form>
      )}

      {tab === 'inject_store' && (
        <form onSubmit={runInjectAndStore}>
          <h2>Inject and store (whitelist enforced)</h2>
          <p style={{ fontSize: '0.9rem', color: '#555', marginBottom: '0.5rem' }}>Source and destination callsigns must be registered.</p>
          <textarea
            value={storeText}
            onChange={(e) => setStoreText(e.target.value)}
            placeholder="Message text…"
            rows={2}
            style={{ width: '100%', maxWidth: 400, padding: '0.5rem', marginBottom: '0.5rem' }}
          />
          <input type="text" value={storeBand} onChange={(e) => setStoreBand(e.target.value)} placeholder="Band (e.g. 40m)" style={{ marginRight: '0.5rem', padding: '0.4rem', width: 80 }} />
          <input type="text" value={storeSource} onChange={(e) => setStoreSource(e.target.value)} placeholder="Source callsign *" style={{ marginRight: '0.5rem', padding: '0.4rem', width: 100 }} />
          <input type="text" value={storeDest} onChange={(e) => setStoreDest(e.target.value)} placeholder="Destination callsign" style={{ marginRight: '0.5rem', padding: '0.4rem', width: 100 }} />
          <br />
          <button type="submit" disabled={submitting || !storeText.trim()} style={{ marginTop: '0.5rem' }}>{submitting ? 'Sending…' : 'Inject & store'}</button>
        </form>
      )}

      {tab === 'relay' && (
        <form onSubmit={runRelay}>
          <h2>{t('messages.relayTitle')}</h2>
          <textarea
            value={relayMessageText}
            onChange={(e) => setRelayMessageText(e.target.value)}
            placeholder={t('messages.messageToRelay')}
            rows={2}
            style={{ width: '100%', maxWidth: 400, padding: '0.5rem', marginBottom: '0.5rem' }}
          />
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
            <input type="text" value={relaySourceBand} onChange={(e) => setRelaySourceBand(e.target.value)} placeholder="Source band" style={{ width: 80, padding: '0.4rem' }} />
            <span>→</span>
            <input type="text" value={relayTargetBand} onChange={(e) => setRelayTargetBand(e.target.value)} placeholder="Target band" style={{ width: 80, padding: '0.4rem' }} />
            <input type="text" value={relaySourceCs} onChange={(e) => setRelaySourceCs(e.target.value)} placeholder="Source callsign" style={{ width: 100, padding: '0.4rem' }} />
            <input type="text" value={relayDestCs} onChange={(e) => setRelayDestCs(e.target.value)} placeholder="Destination callsign" style={{ width: 100, padding: '0.4rem' }} />
          </div>
          <button type="submit" disabled={submitting || !relayMessageText.trim()}>{submitting ? 'Sending…' : 'Relay'}</button>
        </form>
      )}
    </div>
  );
}
