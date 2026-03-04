import React, { useEffect, useState } from 'react';
import { listBands, sendTts } from '../../services/radioshaqApi';

export function RadioPage() {
  const [bands, setBands] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ttsMessage, setTtsMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadBands = () => {
    listBands()
      .then((res) => setBands(res.bands ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load bands'))
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
      setError(e instanceof Error ? e.message : 'Failed to send TTS');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="radio-page">
      <h1>Radio</h1>
      {error && <p role="alert" style={{ color: 'crimson' }}>{error}</p>}

      <section style={{ marginBottom: '1.5rem' }}>
        <h2>Bands</h2>
        <p style={{ marginTop: 0 }}>
          {loading ? <span>Loading…</span> : <span>{bands.length ? bands.join(', ') : 'None'}</span>}
          <button type="button" onClick={loadBands} disabled={loading} style={{ marginLeft: '0.5rem' }}>
            Refresh
          </button>
          <span style={{ marginLeft: '0.5rem', color: '#666', fontSize: '0.85rem' }}>Auto-refresh every 60s</span>
        </p>
      </section>

      <section>
        <h2>Send TTS</h2>
        <p style={{ fontSize: '0.9rem', color: '#555' }}>Send text as speech over the radio (requires radio TX agent).</p>
        <form onSubmit={handleSendTts} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={ttsMessage}
            onChange={(e) => setTtsMessage(e.target.value)}
            placeholder="Message to speak…"
            style={{ padding: '0.4rem', minWidth: 200, flex: 1 }}
            aria-label="TTS message"
          />
          <button type="submit" disabled={submitting || !ttsMessage.trim()}>
            {submitting ? 'Sending…' : 'Send TTS'}
          </button>
        </form>
      </section>

      <p style={{ marginTop: '1.5rem', fontSize: '0.9rem', color: '#555' }}>
        For relay (band translation), use the <strong>Messages</strong> tab → Relay.
      </p>
    </div>
  );
}
