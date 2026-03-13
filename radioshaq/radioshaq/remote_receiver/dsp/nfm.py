"""Narrowband FM (NFM) demodulator utilities for SDR receiver backends.

This is intentionally lightweight: numpy/scipy only, no GNU Radio dependency.
It is good enough for typical ham 2m/70cm analog FM voice channels.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
try:
    from scipy import signal  # type: ignore
except Exception:  # pragma: no cover
    signal = None  # type: ignore


def _require_scipy() -> None:
    if signal is None:
        raise RuntimeError("NFM demod requires SciPy. Install project deps (scipy).")


@dataclass
class NfmConfig:
    """NFM demod configuration."""

    audio_rate_hz: int = 48_000
    # De-emphasis time constant (US): 75 for US, 50 for many EU regions.
    deemphasis_us: float = 75.0
    # Audio low-pass cutoff (voice): ~3 kHz is typical.
    audio_lpf_hz: float = 3_000.0
    # Additional post-demod gain. Keep conservative to avoid clipping.
    audio_gain: float = 2.0


class NfmDemodulator:
    """Stateful NFM demodulator (keeps discriminator history + deemphasis filter state)."""

    def __init__(self, cfg: NfmConfig, rf_rate_hz: int):
        self.cfg = cfg
        self.rf_rate_hz = int(rf_rate_hz)
        self._prev: complex | None = None
        self._de_z: np.ndarray | None = None

    def demod(self, iq: np.ndarray) -> np.ndarray:
        """Demod a chunk of complex IQ into float32 audio in [-1, 1] (approx)."""
        _require_scipy()
        x = np.asarray(iq)
        if x.size < 2:
            return np.zeros(0, dtype=np.float32)
        if not np.iscomplexobj(x):
            x = x.astype(np.complex64)

        # Quadrature discriminator: angle of conjugate product.
        if self._prev is None:
            prev = x[0]
        else:
            prev = self._prev
        y = np.empty(x.size, dtype=np.complex64)
        y[0] = prev
        y[1:] = x[:-1]
        self._prev = x[-1]
        discr = np.angle(x * np.conj(y)).astype(np.float32)

        # Resample discriminator output down to audio rate.
        # Use rational polyphase resampling; works for arbitrary rates.
        audio = signal.resample_poly(discr, up=self.cfg.audio_rate_hz, down=self.rf_rate_hz).astype(
            np.float32
        )

        # Audio low-pass and deemphasis.
        if audio.size == 0:
            return audio
        nyq = 0.5 * self.cfg.audio_rate_hz
        cutoff = min(max(300.0, float(self.cfg.audio_lpf_hz)), nyq * 0.95)
        b, a = signal.butter(4, cutoff / nyq, btype="low")
        audio = signal.lfilter(b, a, audio).astype(np.float32)

        # De-emphasis: simple 1-pole IIR matching RC low-pass with time constant tau.
        tau = float(self.cfg.deemphasis_us) * 1e-6
        if tau > 0:
            # H(z) ~ (1 - alpha) / (1 - alpha z^-1), alpha = exp(-1/(fs*tau))
            alpha = float(np.exp(-1.0 / (self.cfg.audio_rate_hz * tau)))
            b2 = np.array([1.0 - alpha], dtype=np.float32)
            a2 = np.array([1.0, -alpha], dtype=np.float32)
            if self._de_z is None:
                self._de_z = signal.lfilter_zi(b2, a2).astype(np.float32) * 0.0
            audio, self._de_z = signal.lfilter(b2, a2, audio, zi=self._de_z)
            audio = audio.astype(np.float32)

        audio *= float(self.cfg.audio_gain)
        audio = np.clip(audio, -1.0, 1.0)
        return audio


def float_to_pcm16(audio: np.ndarray) -> bytes:
    """Convert float audio [-1,1] to little-endian signed 16-bit PCM bytes."""
    a = np.asarray(audio, dtype=np.float32)
    if a.size == 0:
        return b""
    pcm = (a * 32767.0).astype(np.int16)
    return pcm.tobytes()

