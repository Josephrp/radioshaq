"""Analog FM modulation helpers for SDR transmit.

This is a minimal NFM modulator: audio -> complex baseband FM IQ.
It is intended for demos/testing (2m/70cm analog FM voice).
"""

from __future__ import annotations

import numpy as np
try:
    from scipy import signal  # type: ignore
except Exception:  # pragma: no cover
    signal = None  # type: ignore


def _require_scipy() -> None:
    if signal is None:
        raise RuntimeError("Analog FM modulation requires SciPy. Install project deps (scipy).")


def _to_mono_float(audio: np.ndarray) -> np.ndarray:
    a = np.asarray(audio)
    if a.ndim == 2:
        a = a.mean(axis=1)
    a = a.astype(np.float32, copy=False)
    # Normalize if input looks like int PCM.
    if np.issubdtype(a.dtype, np.integer):
        a = a.astype(np.float32) / 32768.0
    return np.clip(a, -1.0, 1.0)


def nfm_modulate(
    audio: np.ndarray,
    audio_rate_hz: int,
    rf_rate_hz: int,
    *,
    deviation_hz: float = 2_500.0,
    preemphasis_us: float = 75.0,
    audio_lpf_hz: float = 3_000.0,
    gain: float = 0.8,
) -> np.ndarray:
    """Return complex64 FM IQ at rf_rate_hz from audio at audio_rate_hz.

    audio: mono or stereo in [-1,1] float (or PCM-like ints).
    """
    fs_a = int(audio_rate_hz)
    fs_rf = int(rf_rate_hz)
    _require_scipy()
    a = _to_mono_float(audio)
    if a.size == 0:
        return np.zeros(0, dtype=np.complex64)

    # Low-pass audio and apply simple pre-emphasis (inverse of receiver deemphasis).
    nyq = 0.5 * fs_a
    cutoff = min(max(300.0, float(audio_lpf_hz)), nyq * 0.95)
    b, aa = signal.butter(4, cutoff / nyq, btype="low")
    a = signal.lfilter(b, aa, a).astype(np.float32)

    tau = float(preemphasis_us) * 1e-6
    if tau > 0:
        # Pre-emphasis high-pass: H(s)=1 + s*tau approximated via discrete differentiation + leak.
        # Simple approximation: y[n] = x[n] - alpha*x[n-1] + alpha*y[n-1]
        alpha = float(np.exp(-1.0 / (fs_a * tau)))
        y = np.empty_like(a)
        y0 = 0.0
        x1 = a[0]
        for i, x0 in enumerate(a):
            y0 = (x0 - x1) + alpha * y0
            y[i] = y0
            x1 = x0
        a = y

    a *= float(gain)
    a = np.clip(a, -1.0, 1.0)

    # Resample audio to RF sample rate.
    a_rf = signal.resample_poly(a, up=fs_rf, down=fs_a).astype(np.float32)
    if a_rf.size == 0:
        return np.zeros(0, dtype=np.complex64)

    # Integrate frequency deviation to phase. phase[n] = phase[n-1] + 2*pi*dev*x/fs
    k = 2.0 * np.pi * float(deviation_hz) / float(fs_rf)
    phase = np.cumsum(k * a_rf, dtype=np.float64)
    iq = np.exp(1j * phase).astype(np.complex64)
    return iq

