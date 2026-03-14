"""Unit tests for analog DSP (AM/SSB/NFM demod/mod) without hardware."""

from __future__ import annotations

import numpy as np

from radioshaq.radio.analog_mod import am_modulate, ssb_modulate
from radioshaq.radio.fm import nfm_modulate
from radioshaq.remote_receiver.dsp.analog import AnalogConfig, AmDemodulator, SsbDemodulator
from radioshaq.remote_receiver.dsp.nfm import NfmConfig, NfmDemodulator


def _tone(fs: int, hz: float, dur: float = 0.25) -> np.ndarray:
    n = int(fs * dur)
    t = np.arange(n, dtype=np.float32) / float(fs)
    return 0.5 * np.sin(2.0 * np.pi * float(hz) * t).astype(np.float32)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    n = min(a.size, b.size)
    if n <= 10:
        return 0.0
    a = a[:n]
    b = b[:n]
    a = a - float(np.mean(a))
    b = b - float(np.mean(b))
    denom = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


def test_am_demod_recovers_tone() -> None:
    fs_a = 48_000
    fs_rf = 240_000
    audio = _tone(fs_a, 1000.0)
    iq = am_modulate(audio, fs_a, fs_rf, modulation_index=0.7, gain=0.9)
    dem = AmDemodulator(AnalogConfig(audio_rate_hz=fs_a, audio_lpf_hz=3_000, audio_gain=2.0), fs_rf)
    out = dem.demod(iq)
    # Correlation should be positive and reasonably high (phase can flip depending on DC removal)
    assert abs(_corr(audio[2000:], out[2000:])) > 0.4


def test_ssb_usb_demod_recovers_tone() -> None:
    fs_a = 48_000
    fs_rf = 240_000
    audio = _tone(fs_a, 700.0)
    iq = ssb_modulate(audio, fs_a, fs_rf, sideband="USB", gain=0.8)
    dem = SsbDemodulator(AnalogConfig(audio_rate_hz=fs_a, bfo_hz=1500.0, audio_gain=2.0), fs_rf, sideband="USB")
    out = dem.demod(iq)
    assert abs(_corr(audio[2000:], out[2000:])) > 0.3


def test_nfm_demod_recovers_tone() -> None:
    fs_a = 48_000
    fs_rf = 240_000
    audio = _tone(fs_a, 1000.0)
    iq = nfm_modulate(audio, fs_a, fs_rf, deviation_hz=2_500.0)
    dem = NfmDemodulator(NfmConfig(audio_rate_hz=fs_a), rf_rate_hz=fs_rf)
    out = dem.demod(iq)
    assert abs(_corr(audio[2000:], out[2000:])) > 0.3

