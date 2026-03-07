import { useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import {
  getConfigLlm,
  updateConfigLlm,
  getConfigMemory,
  updateConfigMemory,
  getConfigOverrides,
  type LlmConfigResponse,
  type MemoryConfigResponse,
  type ConfigOverridesResponse,
} from '../../services/radioshaqApi';

const SECTION_STYLE: React.CSSProperties = { marginBottom: '1.5rem', padding: '1rem', border: '1px solid #ddd', borderRadius: 8 };
const LABEL_STYLE: React.CSSProperties = { display: 'block', marginBottom: '0.25rem', fontWeight: 500 };
const INPUT_STYLE: React.CSSProperties = { width: '100%', maxWidth: 400, padding: '0.35rem 0.5rem', marginBottom: '0.5rem' };

export function SettingsPage() {
  const { t } = useTranslation();
  const [llm, setLlm] = useState<LlmConfigResponse | null>(null);
  const [memory, setMemory] = useState<MemoryConfigResponse | null>(null);
  const [overrides, setOverrides] = useState<ConfigOverridesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      const [l, m, o] = await Promise.all([getConfigLlm(), getConfigMemory(), getConfigOverrides()]);
      setLlm(l);
      setMemory(m);
      setOverrides(o);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.failedToLoad'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleLlmChange = async (field: keyof LlmConfigResponse, value: string | number | null) => {
    if (!llm) return;
    setSaving('llm');
    try {
      const updated = await updateConfigLlm({ ...llm, [field]: value });
      setLlm(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.failedToUpdateLlm'));
    } finally {
      setSaving(null);
    }
  };

  const handleMemoryChange = async (field: keyof MemoryConfigResponse, value: string | number | boolean | null) => {
    if (!memory) return;
    setSaving('memory');
    try {
      const updated = await updateConfigMemory({ ...memory, [field]: value });
      setMemory(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.failedToUpdateMemory'));
    } finally {
      setSaving(null);
    }
  };

  // Keep until per-role override controls are wired back in:
  // const ROLES = ['orchestrator', 'judge', 'whitelist', 'daily_summary', 'memory'] as const;
  // Future implementation placeholder:
  // const handleOverridesChange = async (
  //   kind: 'llm_overrides' | 'memory_overrides',
  //   role: string,
  //   field: string,
  //   value: unknown
  // ) => {
  //   // Re-enable updateConfigOverrides import and wire controls in "Per-role overrides".
  // };

  if (loading) return <p>{t('common.loading')}</p>;
  if (error) return <p role="alert">{t('common.error')}: {error}</p>;

  const showRestartNotice =
    llm?._meta?.config_applies_after === 'restart' ||
    memory?._meta?.config_applies_after === 'restart' ||
    overrides?._meta?.config_applies_after === 'restart';

  return (
    <div className="settings-page">
      <h1>{t('settings.title')}</h1>
      {showRestartNotice && (
        <p style={{ color: '#666', marginBottom: '1rem' }} role="note">
          {t('settings.configRestartNoticeFull')}
        </p>
      )}

      <section style={SECTION_STYLE}>
        <h2>{t('settings.llm')}</h2>
        {llm && (
          <>
            <label style={LABEL_STYLE}>{t('settings.provider')}</label>
            <select
              style={INPUT_STYLE}
              value={llm.provider ?? 'mistral'}
              onChange={(e) => handleLlmChange('provider', e.target.value)}
              disabled={!!saving}
            >
              <option value="mistral">mistral</option>
              <option value="openai">openai</option>
              <option value="anthropic">anthropic</option>
              <option value="custom">custom</option>
            </select>
            <label style={LABEL_STYLE}>{t('settings.model')}</label>
            <input
              style={INPUT_STYLE}
              type="text"
              value={llm.model ?? ''}
              onChange={(e) => setLlm((p) => (p ? { ...p, model: e.target.value } : p))}
              onBlur={(e) => handleLlmChange('model', e.target.value)}
              placeholder={t('settings.modelPlaceholder')}
              disabled={!!saving}
            />
            <label style={LABEL_STYLE}>{t('settings.customApiBase')}</label>
            <input
              style={INPUT_STYLE}
              type="url"
              value={llm.custom_api_base ?? ''}
              onChange={(e) => setLlm((p) => (p ? { ...p, custom_api_base: e.target.value || null } : p))}
              onBlur={(e) => handleLlmChange('custom_api_base', e.target.value || null)}
              placeholder={t('settings.customApiBasePlaceholder')}
              disabled={!!saving}
            />
            <label style={LABEL_STYLE}>{t('settings.temperature')}</label>
            <input
              style={INPUT_STYLE}
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={llm.temperature ?? 0.1}
              onChange={(e) => setLlm((p) => (p ? { ...p, temperature: parseFloat(e.target.value) || 0.1 } : p))}
              onBlur={(e) => handleLlmChange('temperature', parseFloat(e.target.value) || 0.1)}
              disabled={!!saving}
            />
            <label style={LABEL_STYLE}>{t('settings.maxTokens')}</label>
            <input
              style={INPUT_STYLE}
              type="number"
              min={1}
              value={llm.max_tokens ?? 4096}
              onChange={(e) => setLlm((p) => (p ? { ...p, max_tokens: parseInt(e.target.value, 10) || 4096 } : p))}
              onBlur={(e) => handleLlmChange('max_tokens', parseInt(e.target.value, 10) || 4096)}
              disabled={!!saving}
            />
          </>
        )}
      </section>

      <section style={SECTION_STYLE}>
        <h2>{t('settings.memoryHindsight')}</h2>
        {memory && (
          <>
            <label style={LABEL_STYLE}>
              <input
                type="checkbox"
                checked={memory.enabled ?? true}
                onChange={(e) => handleMemoryChange('enabled', e.target.checked)}
                disabled={!!saving}
              />{' '}
              {t('settings.enabled')}
            </label>
            <label style={LABEL_STYLE}>{t('settings.hindsightBaseUrl')}</label>
            <input
              style={INPUT_STYLE}
              type="url"
              value={memory.hindsight_base_url ?? ''}
              onChange={(e) => setMemory((p) => (p ? { ...p, hindsight_base_url: e.target.value } : p))}
              onBlur={(e) => handleMemoryChange('hindsight_base_url', e.target.value)}
              placeholder={t('settings.hindsightBaseUrlPlaceholder')}
              disabled={!!saving}
            />
            <label style={LABEL_STYLE}>
              <input
                type="checkbox"
                checked={memory.hindsight_enabled ?? true}
                onChange={(e) => handleMemoryChange('hindsight_enabled', e.target.checked)}
                disabled={!!saving}
              />{' '}
              {t('settings.hindsightEnabled')}
            </label>
            <label style={LABEL_STYLE}>{t('settings.embeddingModelOptional')}</label>
            <input
              style={INPUT_STYLE}
              type="text"
              value={memory.hindsight_embedding_model ?? ''}
              onChange={(e) => setMemory((p) => (p ? { ...p, hindsight_embedding_model: e.target.value || null } : p))}
              onBlur={(e) => handleMemoryChange('hindsight_embedding_model', e.target.value || null)}
              placeholder={t('settings.embeddingModelPlaceholder')}
              disabled={!!saving}
            />
          </>
        )}
      </section>

      <section style={SECTION_STYLE}>
        <h2>{t('settings.overrides')}</h2>
        <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
          <Trans i18nKey="settings.perRoleOverridesIntro" components={{ strong: <strong /> }} />
        </p>
        {overrides && (
          <pre style={{ background: '#f5f5f5', padding: '0.75rem', borderRadius: 4, overflow: 'auto', fontSize: '0.85rem' }}>
            {JSON.stringify({ llm_overrides: overrides.llm_overrides ?? {}, memory_overrides: overrides.memory_overrides ?? {} }, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}
