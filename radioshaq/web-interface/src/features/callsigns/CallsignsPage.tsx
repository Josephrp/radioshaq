import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  listCallsigns,
  registerCallsign,
  unregisterCallsign,
  registerCallsignFromAudio,
  setOperatorLocation,
  type CallsignEntry,
} from '../../services/radioshaqApi';
import { OperatorMap } from '../../components/maps/OperatorMap';

export function CallsignsPage() {
  const { t } = useTranslation();
  const [list, setList] = useState<CallsignEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addCallsign, setAddCallsign] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioCallsign, setAudioCallsign] = useState('');
  const [setLocationCallsign, setSetLocationCallsign] = useState<string | null>(null);
  const [setLocationLat, setSetLocationLat] = useState('');
  const [setLocationLng, setSetLocationLng] = useState('');
  const [setLocationSubmitting, setSetLocationSubmitting] = useState(false);
  const [setLocationError, setSetLocationError] = useState<string | null>(null);
  const [setLocationSuccess, setSetLocationSuccess] = useState(false);

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

  const handleSetLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    const cs = setLocationCallsign?.trim().toUpperCase();
    if (!cs) return;
    const lat = parseFloat(setLocationLat);
    const lng = parseFloat(setLocationLng);
    if (Number.isNaN(lat) || lat < -90 || lat > 90) {
      setSetLocationError(t('map.latInvalid') ?? 'Latitude must be between -90 and 90.');
      return;
    }
    if (Number.isNaN(lng) || lng < -180 || lng > 180) {
      setSetLocationError(t('map.lngInvalid') ?? 'Longitude must be between -180 and 180.');
      return;
    }
    setSetLocationSubmitting(true);
    setSetLocationError(null);
    setSetLocationSuccess(false);
    try {
      await setOperatorLocation({ callsign: cs, latitude: lat, longitude: lng });
      setSetLocationSuccess(true);
      setTimeout(() => {
        setSetLocationCallsign(null);
        setSetLocationLat('');
        setSetLocationLng('');
        setSetLocationSuccess(false);
      }, 1500);
    } catch (err) {
      setSetLocationError(err instanceof Error ? err.message : t('common.failed'));
    } finally {
      setSetLocationSubmitting(false);
    }
  };

  const openSetLocation = (callsign: string) => {
    const cs = typeof callsign === 'string' ? callsign : (callsign as CallsignEntry).callsign;
    if (cs) {
      setSetLocationCallsign(String(cs));
      setSetLocationLat('');
      setSetLocationLng('');
      setSetLocationError(null);
      setSetLocationSuccess(false);
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
                  <button type="button" onClick={() => openSetLocation(String(cs))} style={{ fontSize: '0.85rem' }}>
                    {t('map.setLocation') ?? 'Set location'}
                  </button>
                  <button type="button" onClick={() => handleRemove(String(cs))} style={{ fontSize: '0.85rem' }}>
                    {t('callsigns.remove')}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {setLocationCallsign && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t('map.setLocation') ?? 'Set location'}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setSetLocationCallsign(null)}
        >
          <div
            style={{
              background: '#fff',
              padding: '1.5rem',
              borderRadius: 8,
              maxWidth: 420,
              width: '90vw',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginTop: 0 }}>{t('map.setLocation') ?? 'Set location'} – {setLocationCallsign}</h3>
            {setLocationError && (
              <p role="alert" style={{ color: 'crimson', fontSize: '0.9rem' }}>{setLocationError}</p>
            )}
            {setLocationSuccess && (
              <p style={{ color: '#2e7d32', fontSize: '0.9rem' }}>{t('map.locationUpdated')}</p>
            )}
            <form onSubmit={handleSetLocation} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <label style={{ fontSize: '0.9rem' }}>
                {t('map.lat') ?? 'Latitude'} (-90 to 90)
                <input
                  type="text"
                  value={setLocationLat}
                  onChange={(e) => setSetLocationLat(e.target.value)}
                  placeholder="e.g. 40.71"
                  style={{ display: 'block', marginTop: 2, padding: '0.35rem', width: '100%' }}
                />
              </label>
              <label style={{ fontSize: '0.9rem' }}>
                {t('map.lng') ?? 'Longitude'} (-180 to 180)
                <input
                  type="text"
                  value={setLocationLng}
                  onChange={(e) => setSetLocationLng(e.target.value)}
                  placeholder="e.g. -74.00"
                  style={{ display: 'block', marginTop: 2, padding: '0.35rem', width: '100%' }}
                />
              </label>
              {setLocationLat && setLocationLng && !Number.isNaN(parseFloat(setLocationLat)) && !Number.isNaN(parseFloat(setLocationLng)) && (
                <div style={{ height: 160, borderRadius: 4, overflow: 'hidden' }}>
                  <OperatorMap
                    center={{
                      lat: Math.max(-90, Math.min(90, parseFloat(setLocationLat) || 0)),
                      lng: Math.max(-180, Math.min(180, parseFloat(setLocationLng) || 0)),
                    }}
                    zoom={6}
                    markers={[{
                      id: 'preview',
                      position: {
                        lat: Math.max(-90, Math.min(90, parseFloat(setLocationLat) || 0)),
                        lng: Math.max(-180, Math.min(180, parseFloat(setLocationLng) || 0)),
                      },
                      label: setLocationCallsign,
                    }]}
                    height={160}
                  />
                </div>
              )}
              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setSetLocationCallsign(null)}>
                  {t('common.cancel')}
                </button>
                <button type="submit" disabled={setLocationSubmitting}>
                  {setLocationSubmitting ? t('common.loading') : (t('map.updateLocation') ?? 'Update location')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
