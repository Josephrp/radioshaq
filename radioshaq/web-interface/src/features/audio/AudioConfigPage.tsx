import { useEffect, useState } from 'react';
import { AudioActivationMode, ResponseMode } from '../../types/audio';
import { ResponseModeSelector } from '../../components/audio/ResponseModeSelector';
import { ConfirmationQueue } from '../../components/audio/ConfirmationQueue';
import { VADVisualizer } from '../../components/audio/VADVisualizer';
import {
  getAudioConfig,
  updateAudioConfig,
  listAudioDevices,
  listPendingResponses,
} from '../../services/radioshaqApi';
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

  // Live polling: pending queue when in confirm mode
  useEffect(() => {
    const mode = config?.response_mode;
    if (mode !== 'confirm_first' && mode !== 'confirm_timeout') return;
    const interval = setInterval(loadPending, 5000);
    return () => clearInterval(interval);
  }, [config?.response_mode]);

  const handleResponseModeChange = async (mode: ResponseMode) => {
    if (!config) return;
    try {
      const updated = await updateAudioConfig({ response_mode: mode });
      setConfig(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update');
    }
  };

  const handleAudioActivationChange = async (patch: {
    audio_activation_enabled?: boolean;
    audio_activation_phrase?: string;
    audio_activation_mode?: AudioActivationMode;
  }) => {
    if (!config) return;
    try {
      const updated = await updateAudioConfig(patch);
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
      <h1>RadioShaq Audio</h1>

      <section>
        <h2>Response mode</h2>
        <ResponseModeSelector
          value={config.response_mode}
          onChange={handleResponseModeChange}
        />
      </section>

      <section>
        <h2>Audio activation</h2>
        <p>
          <label>
            <input
              type="checkbox"
              checked={config.audio_activation_enabled ?? false}
              onChange={(e) =>
                handleAudioActivationChange({
                  audio_activation_enabled: e.target.checked,
                })
              }
            />{' '}
            Require activation phrase before processing
          </label>
        </p>
        {config.audio_activation_enabled && (
          <>
            <p>
              <label>
                Phrase:{' '}
                <input
                  type="text"
                  value={config.audio_activation_phrase ?? 'radioshaq'}
                  onChange={(e) =>
                    handleAudioActivationChange({
                      audio_activation_phrase: e.target.value,
                    })
                  }
                  placeholder="radioshaq"
                />
              </label>
            </p>
            <p>
              <label>
                Mode:{' '}
                <select
                  value={config.audio_activation_mode ?? AudioActivationMode.SESSION}
                  onChange={(e) =>
                    handleAudioActivationChange({
                      audio_activation_mode: e.target
                        .value as AudioActivationMode,
                    })
                  }
                >
                  <option value={AudioActivationMode.SESSION}>Session (once heard, stay active)</option>
                  <option value={AudioActivationMode.PER_MESSAGE}>Per-message (require phrase each time)</option>
                </select>
              </label>
            </p>
          </>
        )}
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
