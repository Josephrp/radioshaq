import { useEffect, useState } from 'react';
import {
  getConfigLlm,
  updateConfigLlm,
  getConfigMemory,
  updateConfigMemory,
  getConfigOverrides,
  updateConfigOverrides,
  type LlmConfigResponse,
  type MemoryConfigResponse,
  type ConfigOverridesResponse,
} from '../../services/radioshaqApi';

const SECTION_STYLE: React.CSSProperties = { marginBottom: '1.5rem', padding: '1rem', border: '1px solid #ddd', borderRadius: 8 };
const LABEL_STYLE: React.CSSProperties = { display: 'block', marginBottom: '0.25rem', fontWeight: 500 };
const INPUT_STYLE: React.CSSProperties = { width: '100%', maxWidth: 400, padding: '0.35rem 0.5rem', marginBottom: '0.5rem' };

export function SettingsPage() {
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
      setError(e instanceof Error ? e.message : 'Failed to load config');
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
      setError(e instanceof Error ? e.message : 'Failed to update LLM');
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
      setError(e instanceof Error ? e.message : 'Failed to update memory');
    } finally {
      setSaving(null);
    }
  };

  const handleOverridesChange = async (kind: 'llm_overrides' | 'memory_overrides', role: string, field: string, value: unknown) => {
    if (!overrides) return;
    setSaving('overrides');
    try {
      const current = overrides[kind] || {};
      const roleObj = { ...(current[role] || {}), [field]: value };
      const next = { ...current, [role]: roleObj };
      const updated = await updateConfigOverrides({ ...overrides, [kind]: next });
      setOverrides(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update overrides');
    } finally {
      setSaving(null);
    }
  };

  // Keep this handler compiled until override edit controls are wired back in.
  void handleOverridesChange;

  if (loading) return <p>Loading…</p>;
  if (error) return <p role="alert">Error: {error}</p>;

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        LLM, memory (Hindsight), and per-role overrides. Changes are runtime overlays and do not persist to config file until you save there.
      </p>

      <section style={SECTION_STYLE}>
        <h2>LLM</h2>
        {llm && (
          <>
            <label style={LABEL_STYLE}>Provider</label>
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
            <label style={LABEL_STYLE}>Model</label>
            <input
              style={INPUT_STYLE}
              type="text"
              value={llm.model ?? ''}
              onChange={(e) => setLlm((p) => (p ? { ...p, model: e.target.value } : p))}
              onBlur={(e) => handleLlmChange('model', e.target.value)}
              placeholder="e.g. mistral-large-latest, ollama/llama2"
              disabled={!!saving}
            />
            <label style={LABEL_STYLE}>Custom API base (e.g. Ollama)</label>
            <input
              style={INPUT_STYLE}
              type="url"
              value={llm.custom_api_base ?? ''}
              onChange={(e) => setLlm((p) => (p ? { ...p, custom_api_base: e.target.value || null } : p))}
              onBlur={(e) => handleLlmChange('custom_api_base', e.target.value || null)}
              placeholder="http://localhost:11434"
              disabled={!!saving}
            />
            <label style={LABEL_STYLE}>Temperature</label>
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
            <label style={LABEL_STYLE}>Max tokens</label>
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
        <h2>Memory (Hindsight)</h2>
        {memory && (
          <>
            <label style={LABEL_STYLE}>
              <input
                type="checkbox"
                checked={memory.enabled ?? true}
                onChange={(e) => handleMemoryChange('enabled', e.target.checked)}
                disabled={!!saving}
              />{' '}
              Enabled
            </label>
            <label style={LABEL_STYLE}>Hindsight base URL</label>
            <input
              style={INPUT_STYLE}
              type="url"
              value={memory.hindsight_base_url ?? ''}
              onChange={(e) => setMemory((p) => (p ? { ...p, hindsight_base_url: e.target.value } : p))}
              onBlur={(e) => handleMemoryChange('hindsight_base_url', e.target.value)}
              placeholder="http://localhost:8888"
              disabled={!!saving}
            />
            <label style={LABEL_STYLE}>
              <input
                type="checkbox"
                checked={memory.hindsight_enabled ?? true}
                onChange={(e) => handleMemoryChange('hindsight_enabled', e.target.checked)}
                disabled={!!saving}
              />{' '}
              Hindsight enabled
            </label>
            <label style={LABEL_STYLE}>Embedding model (optional)</label>
            <input
              style={INPUT_STYLE}
              type="text"
              value={memory.hindsight_embedding_model ?? ''}
              onChange={(e) => setMemory((p) => (p ? { ...p, hindsight_embedding_model: e.target.value || null } : p))}
              onBlur={(e) => handleMemoryChange('hindsight_embedding_model', e.target.value || null)}
              placeholder="If Hindsight supports it"
              disabled={!!saving}
            />
          </>
        )}
      </section>

      <section style={SECTION_STYLE}>
        <h2>Per-role overrides</h2>
        <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
          Roles: orchestrator, judge, whitelist, daily_summary, memory. You can also use any <strong>agent name</strong> (e.g. whitelist, gis, radio_tx, scheduler) for per-subagent LLM; only whitelist uses an LLM today.
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
