import React, { useEffect, useState } from 'react';
import { ResponseMode } from '../../types/audio';
import { ResponseModeSelector } from '../../components/audio/ResponseModeSelector';
import { ConfirmationQueue } from '../../components/audio/ConfirmationQueue';
import { VADVisualizer } from '../../components/audio/VADVisualizer';
import {
  getAudioConfig,
  updateAudioConfig,
  listAudioDevices,
  listPendingResponses,
} from '../../services/shakodsApi';
import type { AudioConfig, PendingResponse } from '../../types/audio';

export function AudioConfigPage() {
  const [config, setConfig] = useState<AudioConfig | null>(null);
  const [pending, setPending] = useState<PendingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConfig = async () => {
    try {
      const c = await getAudioConfig();
      setConfig(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load config');
    }
  };

  const loadPending = async () => {
    try {
      const res = await listPendingResponses();
      setPending(res.pending_responses ?? []);
    } catch {
      setPending([]);
    }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([loadConfig(), loadPending()]);
      setLoading(false);
    })();
  }, []);

  const handleResponseModeChange = async (mode: ResponseMode) => {
    if (!config) return;
    try {
      const updated = await updateAudioConfig({ response_mode: mode });
      setConfig(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update');
    }
  };

  const [devices, setDevices] = useState<{ input_devices: { index: number; name: string }[]; output_devices: { index: number; name: string }[] } | null>(null);
  useEffect(() => {
    listAudioDevices().then(setDevices).catch(() => setDevices(null));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p role="alert">Error: {error}</p>;
  if (!config) return null;

  return (
    <div className="audio-config-page">
      <h1>SHAKODS Audio</h1>

      <section>
        <h2>Response mode</h2>
        <ResponseModeSelector
          value={config.response_mode}
          onChange={handleResponseModeChange}
        />
      </section>

      {devices && (
        <section>
          <h2>Audio devices</h2>
          <p>Inputs: {devices.input_devices?.length ?? 0} — Outputs: {devices.output_devices?.length ?? 0}</p>
        </section>
      )}

      <section>
        <h2>VAD / metrics</h2>
        <VADVisualizer sessionId="live" />
      </section>

      {(config.response_mode === 'confirm_first' || config.response_mode === 'confirm_timeout') && (
        <section>
          <h2>Confirmation queue</h2>
          <ConfirmationQueue
            pending={pending}
            onRefresh={loadPending}
          />
        </section>
      )}
    </div>
  );
}
