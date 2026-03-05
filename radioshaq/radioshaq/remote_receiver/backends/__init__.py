"""SDR backends (RTL-SDR, HackRF) for remote receiver."""

from radioshaq.remote_receiver.backends.base import SDRBackend
from radioshaq.remote_receiver.backends.rtlsdr_backend import RtlSdrBackend
from radioshaq.remote_receiver.backends.hackrf_backend import HackRFBackend

__all__ = ["SDRBackend", "RtlSdrBackend", "HackRFBackend"]
