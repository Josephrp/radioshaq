import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { searchTranscripts, playTranscript, type TranscriptItem } from '../../services/radioshaqApi';

export function TranscriptsPage() {
  const { t } = useTranslation();
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [callsign, setCallsign] = useState('');
  const [band, setBand] = useState('');
  const [destinationOnly, setDestinationOnly] = useState(false);
  const [limit, setLimit] = useState(50);
  const [playingId, setPlayingId] = useState<number | null>(null);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await searchTranscripts({
        callsign: callsign.trim() || undefined,
        band: band.trim() || undefined,
        destination_only: destinationOnly,
        limit,
      });
      setTranscripts(res.transcripts ?? []);
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : t('common.failedToLoad'));
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Live polling: silent refresh every 10s (uses current filters)
  useEffect(() => {
    const interval = setInterval(() => load(true), 10000);
    return () => clearInterval(interval);
  }, [callsign, band, destinationOnly, limit]);

  const handlePlay = async (id: number) => {
    setError(null);
    setPlayingId(id);
    try {
      await playTranscript(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setPlayingId(null);
    }
  };

  const idOf = (t: TranscriptItem): number =>
    Number(t.id ?? (t as Record<string, unknown>).transcript_id ?? 0);

  return (
    <div className="transcripts-page">
      <h1>{t('transcripts.title')}</h1>
      {error && <p role="alert" style={{ color: 'crimson' }}>{error}</p>}

      <section style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          value={callsign}
          onChange={(e) => setCallsign(e.target.value)}
          placeholder="Filter by callsign"
          style={{ padding: '0.4rem', width: 120 }}
        />
        <input
          type="text"
          value={band}
          onChange={(e) => setBand(e.target.value)}
          placeholder="Filter by band"
          style={{ padding: '0.4rem', width: 80 }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <input
            type="checkbox"
            checked={destinationOnly}
            onChange={(e) => setDestinationOnly(e.target.checked)}
          />
          Only messages for me
        </label>
        <input
          type="number"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value) || 50)}
          min={1}
          max={500}
          style={{ padding: '0.4rem', width: 60 }}
        />
        <button type="button" onClick={() => load()} disabled={loading}>{loading ? 'Loading…' : 'Search'}</button>
        <span style={{ marginLeft: '0.5rem', color: '#666', fontSize: '0.85rem' }}>Auto-refresh every 10s</span>
      </section>

      {loading ? (
        <p>Loading…</p>
      ) : transcripts.length === 0 ? (
        <p>No transcripts found.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {transcripts.map((t) => {
            const id = idOf(t);
            const text = t.transcript_text ?? (t as Record<string, unknown>).transcript_text ?? '';
            const src = t.source_callsign ?? (t as Record<string, unknown>).source_callsign ?? '?';
            return (
              <li
                key={id}
                style={{
                  border: '1px solid #eee',
                  borderRadius: 4,
                  padding: '0.5rem 0.75rem',
                  marginBottom: '0.5rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong>[{id}]</strong> {String(src)}: {(String(text)).slice(0, 80)}{(String(text)).length > 80 ? '…' : ''}
                </div>
                <button
                  type="button"
                  onClick={() => handlePlay(id)}
                  disabled={playingId !== null}
                  style={{ flexShrink: 0 }}
                >
                  {playingId === id ? 'Playing…' : 'Play over radio'}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
