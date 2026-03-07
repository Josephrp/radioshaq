import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  listCallsigns,
  registerCallsign,
  unregisterCallsign,
  registerCallsignFromAudio,
  type CallsignEntry,
} from '../../services/radioshaqApi';

export function CallsignsPage() {
  const { t } = useTranslation();
  const [list, setList] = useState<CallsignEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addCallsign, setAddCallsign] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioCallsign, setAudioCallsign] = useState('');

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await listCallsigns();
      setList(res.registered ?? []);
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : t('callsigns.failedToLoad'));
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Live polling: silent refresh every 20s
  useEffect(() => {
    const interval = setInterval(() => load(true), 20000);
    return () => clearInterval(interval);
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const cs = addCallsign.trim().toUpperCase();
    if (!cs) return;
    setSubmitting(true);
    setError(null);
    try {
      await registerCallsign(cs, 'api');
      setAddCallsign('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('callsigns.failedToAdd'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemove = async (callsign: string) => {
    const cs = typeof callsign === 'string' ? callsign : (callsign as CallsignEntry).callsign;
    if (!cs) return;
    setError(null);
    try {
      await unregisterCallsign(cs);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('callsigns.failedToRemove'));
    }
  };

  const handleRegisterFromAudio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!audioFile) {
      setError(t('callsigns.selectAudio'));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await registerCallsignFromAudio(audioFile, audioCallsign.trim() || undefined);
      setAudioFile(null);
      setAudioCallsign('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('callsigns.failedRegisterAudio'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <p>{t('common.loading')}</p>;

  return (
    <div className="callsigns-page">
      <h1>{t('callsigns.whitelistTitle')}</h1>
      {error && <p role="alert" style={{ color: 'crimson' }}>{error}</p>}

      <section style={{ marginBottom: '1.5rem' }}>
        <h2>{t('callsigns.addCallsign')}</h2>
        <form onSubmit={handleAdd} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={addCallsign}
            onChange={(e) => setAddCallsign(e.target.value)}
            placeholder="e.g. K5ABC"
            maxLength={10}
            style={{ padding: '0.4rem', width: 120 }}
            aria-label={t('callsigns.addPlaceholder')}
          />
          <button type="submit" disabled={submitting || !addCallsign.trim()}>
            {submitting ? t('callsigns.adding') : t('callsigns.add')}
          </button>
        </form>
      </section>

      <section style={{ marginBottom: '1.5rem' }}>
        <h2>{t('callsigns.registerFromAudio')}</h2>
        <form onSubmit={handleRegisterFromAudio} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: 400 }}>
          <input
            type="file"
            accept="audio/*"
            onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
            aria-label={t('callsigns.selectAudio')}
          />
          <input
            type="text"
            value={audioCallsign}
            onChange={(e) => setAudioCallsign(e.target.value)}
            placeholder={t('callsigns.confirmCallsignPlaceholder')}
            maxLength={10}
            style={{ padding: '0.4rem' }}
          />
          <button type="submit" disabled={submitting || !audioFile}>
            {submitting ? t('callsigns.uploading') : t('callsigns.submitAudio')}
          </button>
        </form>
      </section>

      <section>
        <h2>{t('callsigns.registeredCount', { count: list.length })}</h2>
        <p style={{ marginTop: 0, fontSize: '0.9rem' }}>
          <button type="button" onClick={() => load()} disabled={loading}>
            {loading ? t('callsigns.refreshing') : t('common.refresh')}
          </button>
          <span style={{ marginLeft: '0.5rem', color: '#666' }}>{t('callsigns.autoRefresh20')}</span>
        </p>
        {list.length === 0 ? (
          <p>{t('callsigns.noCallsigns')}</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {list.map((entry, i) => {
              const cs = typeof entry === 'string' ? entry : (entry.callsign ?? (entry as Record<string, unknown>).callsign);
              const key = typeof cs === 'string' ? cs : `c-${i}`;
              return (
                <li key={key} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <span>{String(cs)}</span>
                  <button type="button" onClick={() => handleRemove(String(cs))} style={{ fontSize: '0.85rem' }}>
                    {t('callsigns.remove')}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
