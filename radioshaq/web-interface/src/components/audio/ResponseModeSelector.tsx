import React from 'react';
import { ResponseMode } from '../../types/audio';

interface ResponseModeSelectorProps {
  value: ResponseMode;
  onChange: (mode: ResponseMode) => void;
  disabled?: boolean;
}

const LABELS: Record<ResponseMode, string> = {
  [ResponseMode.LISTEN_ONLY]: 'Listen only (no TX)',
  [ResponseMode.CONFIRM_FIRST]: 'Confirm first (human approval)',
  [ResponseMode.CONFIRM_TIMEOUT]: 'Confirm with timeout (auto-send if not rejected)',
  [ResponseMode.AUTO_RESPOND]: 'Auto-respond (use with caution)',
};

export function ResponseModeSelector({ value, onChange, disabled }: ResponseModeSelectorProps) {
  return (
    <div className="response-mode-selector">
      <label>Response mode</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as ResponseMode)}
        disabled={disabled}
        aria-label="Response mode"
      >
        {(Object.keys(LABELS) as ResponseMode[]).map((mode) => (
          <option key={mode} value={mode}>
            {LABELS[mode]}
          </option>
        ))}
      </select>
    </div>
  );
}
