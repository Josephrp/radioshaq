"""Analog modulation helpers for SDR transmit (AM/SSB/CW-tone).

These functions generate complex baseband IQ for a HackRF-class SDR.
They prioritize portability (numpy/scipy only) over maximum RF fidelity.
"""

from __future__ import annotations

import numpy as np
try:
    from scipy import signal  # type: ignore
except Exception:  # pragma: no cover
    signal = None  # type: ignore


def _require_scipy() -> None:
    if signal is None:
        raise RuntimeError("Analog modulation requires SciPy. Install project deps (scipy).")


def _to_mono_float(audio: np.ndarray) -> np.ndarray:
    a = np.asarray(audio)
    if a.ndim == 2:
        a = a.mean(axis=1)
    if np.issubdtype(a.dtype, np.integer):
        # Assume int16-like PCM.
        a = a.astype(np.float32) / 32768.0
    else:
        a = a.astype(np.float32, copy=False)
    return np.clip(a, -1.0, 1.0)


def _lpf(audio: np.ndarray, fs: int, cutoff_hz: float) -> np.ndarray:
    if audio.size == 0:
        return audio.astype(np.float32)
    nyq = 0.5 * fs
    cutoff = min(max(200.0, float(cutoff_hz)), nyq * 0.95)
    b, a = signal.butter(4, cutoff / nyq, btype="low")
    return signal.lfilter(b, a, audio).astype(np.float32)


def am_modulate(
    audio: np.ndarray,
    audio_rate_hz: int,
    rf_rate_hz: int,
    *,
    modulation_index: float = 0.6,
    audio_lpf_hz: float = 3_000.0,
    gain: float = 0.8,
) -> np.ndarray:
    """AM (DSB-LC) modulation: (1 + m*x) * carrier."""
    _require_scipy()
    fs_a = int(audio_rate_hz)
    fs_rf = int(rf_rate_hz)
    x = _to_mono_float(audio)
    x = _lpf(x, fs_a, audio_lpf_hz)
    x_rf = signal.resample_poly(x, up=fs_rf, down=fs_a).astype(np.float32)
    if x_rf.size == 0:
        return np.zeros(0, dtype=np.complex64)
    m = float(np.clip(modulation_index, 0.0, 1.0))
    env = 1.0 + m * x_rf
    env = np.clip(env, 0.0, 2.0)
    iq = (env * float(gain)).astype(np.complex64)
    return iq


def ssb_modulate(
    audio: np.ndarray,
    audio_rate_hz: int,
    rf_rate_hz: int,
    *,
    sideband: str = "USB",
    audio_lpf_hz: float = 2_800.0,
    carrier: float = 0.0,
    gain: float = 0.8,
) -> np.ndarray:
    """SSB modulation (suppressed carrier by default) using analytic signal (Hilbert)."""
    _require_scipy()
    fs_a = int(audio_rate_hz)
    fs_rf = int(rf_rate_hz)
    x = _to_mono_float(audio)
    x = _lpf(x, fs_a, audio_lpf_hz)
    if x.size == 0:
        return np.zeros(0, dtype=np.complex64)
    # Create analytic baseband at audio rate.
    analytic = signal.hilbert(x).astype(np.complex64)
    side = str(sideband).upper()
    if side == "LSB":
        analytic = np.conj(analytic)
    # Resample complex to RF.
    iq = signal.resample_poly(analytic, up=fs_rf, down=fs_a).astype(np.complex64)
    if carrier:
        iq = iq + complex(float(carrier), 0.0)
    iq *= float(gain)
    # Keep within [-1,1] envelope-ish to avoid int8 clipping later.
    mag = np.max(np.abs(iq)) if iq.size else 1.0
    if mag > 1.0:
        iq = (iq / mag).astype(np.complex64)
    return iq


def cw_tone_iq(
    duration_sec: float,
    rf_rate_hz: int,
    *,
    gain: float = 0.6,
) -> np.ndarray:
    """Generate a simple continuous carrier (CW tone at RF center)."""
    fs = int(rf_rate_hz)
    n = max(0, int(duration_sec * fs))
    if n == 0:
        return np.zeros(0, dtype=np.complex64)
    return (np.ones(n, dtype=np.complex64) * complex(float(gain), 0.0)).astype(np.complex64)

