import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
import type { AudioConfigResponse } from '../../services/radioshaqApi';
import type { PendingResponse } from '../../types/audio';

const ASR_LANGUAGE_OPTIONS = [
  { value: 'auto', labelKey: 'audio.asrLanguageAuto' },
  { value: 'en', labelKey: 'audio.languageEn' },
  { value: 'fr', labelKey: 'audio.languageFr' },
  { value: 'es', labelKey: 'audio.languageEs' },
] as const;

export function AudioConfigPage() {
  const { t } = useTranslation();
  const [config, setConfig] = useState<AudioConfigResponse | null>(null);
  const [pending, setPending] = useState<PendingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConfig = async () => {
    try {
      const c = await getAudioConfig();
      setConfig(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToLoad'));
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
      setError(e instanceof Error ? e.message : t('common.failedToUpdate'));
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
      setError(e instanceof Error ? e.message : t('common.failedToUpdate'));
    }
  };

  const handleAsrLanguageChange = async (asr_language: string) => {
    if (!config) return;
    try {
      const updated = await updateAudioConfig({ asr_language });
      setConfig(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToUpdate'));
    }
  };

  const [devices, setDevices] = useState<{ input_devices: { index: number; name: string }[]; output_devices: { index: number; name: string }[] } | null>(null);
  useEffect(() => {
    listAudioDevices().then(setDevices).catch(() => setDevices(null));
  }, []);

  if (loading) return <p>{t('common.loading')}</p>;
  if (error) return <p role="alert">{t('common.error')}: {error}</p>;
  if (!config) return null;

  const showRestartNotice = config?._meta?.config_applies_after === 'restart';

  return (
    <div className="audio-config-page">
      <h1>{t('audio.title')}</h1>
      {showRestartNotice && (
        <p style={{ fontSize: '0.9rem', color: '#555', marginTop: 0 }} role="note">
          {t('common.configRestartNotice')}
        </p>
      )}

      <section>
        <h2>{t('audio.asrLanguage')}</h2>
        <p>
          <label>
            <select
              value={config.asr_language ?? 'en'}
              onChange={(e) => handleAsrLanguageChange(e.target.value)}
              style={{ padding: '0.35rem 0.5rem', minWidth: 140 }}
            >
              {ASR_LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {t(opt.labelKey)}
                </option>
              ))}
            </select>
          </label>
        </p>
      </section>

      <section>
        <h2>{t('audio.responseMode')}</h2>
        <ResponseModeSelector
          value={config.response_mode}
          onChange={handleResponseModeChange}
        />
      </section>

      <section>
        <h2>{t('audio.audioActivation')}</h2>
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
            {t('audio.requireActivationPhrase')}
          </label>
        </p>
        {config.audio_activation_enabled && (
          <>
            <p>
              <label>
                {t('audio.phrase')}:{' '}
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
                {t('audio.mode')}:{' '}
                <select
                  value={config.audio_activation_mode ?? AudioActivationMode.SESSION}
                  onChange={(e) =>
                    handleAudioActivationChange({
                      audio_activation_mode: e.target
                        .value as AudioActivationMode,
                    })
                  }
                >
                  <option value={AudioActivationMode.SESSION}>{t('audio.sessionOnce')}</option>
                  <option value={AudioActivationMode.PER_MESSAGE}>{t('audio.perMessage')}</option>
                </select>
              </label>
            </p>
          </>
        )}
      </section>

      {devices && (
        <section>
          <h2>{t('audio.audioDevices')}</h2>
          <p>{t('audio.inputs')}: {devices.input_devices?.length ?? 0} — {t('audio.outputs')}: {devices.output_devices?.length ?? 0}</p>
        </section>
      )}

      <section>
        <h2>{t('audio.vadMetrics')}</h2>
        <VADVisualizer sessionId="live" />
      </section>

      {(config.response_mode === 'confirm_first' || config.response_mode === 'confirm_timeout') && (
        <section>
          <h2>{t('audio.confirmationQueue')}</h2>
          <ConfirmationQueue
            pending={pending}
            onRefresh={loadPending}
          />
        </section>
      )}
    </div>
  );
}
