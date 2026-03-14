#!/usr/bin/env python3
"""Decode FT8 from a WAV file using WSJT-X's `jt9` CLI (bridge approach).

This is a tooling hook, not a full in-process FT8 decoder.

Example:
  uv run python scripts/demo/ft8_decode_wav.py --wav in.wav
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Decode FT8 from WAV using jt9 CLI.")
    ap.add_argument("--wav", required=True, help="Path to WAV file (audio baseband).")
    ap.add_argument("--jt9", default="jt9", help="jt9 executable (default: jt9 in PATH).")
    ap.add_argument("--rx-frequency", type=int, default=1500, help="FT8 decode audio offset in Hz (jt9 -f).")
    args = ap.parse_args()

    wav_path = Path(args.wav)
    if not wav_path.exists():
        print(f"WAV not found: {wav_path}", file=sys.stderr)
        return 2

    exe = args.jt9
    if shutil.which(exe) is None:
        print(
            f"jt9 executable not found ({exe!r}). Install WSJT-X tooling and ensure jt9 is on PATH.",
            file=sys.stderr,
        )
        return 3

    cmd = [exe, "-8", "-f", str(args.rx_frequency), str(wav_path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.stdout.strip():
        print(p.stdout.strip())
    if p.stderr.strip():
        print(p.stderr.strip(), file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())

