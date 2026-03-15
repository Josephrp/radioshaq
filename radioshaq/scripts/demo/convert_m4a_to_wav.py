#!/usr/bin/env python3
"""Convert M4A (and other formats) to WAV for demo recordings.

Uses pydub (ffmpeg required on PATH for M4A). Output is written next to
each input file with the same stem and .wav extension.

Examples:
  uv run python scripts/demo/convert_m4a_to_wav.py recordings/06_orchestrator_process.m4a
  uv run python scripts/demo/convert_m4a_to_wav.py recordings/*.m4a
  uv run python scripts/demo/convert_m4a_to_wav.py --dir recordings
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def convert_to_wav(path: Path, overwrite: bool = False) -> bool:
    """Convert one audio file to WAV (same dir, same stem). Returns True on success."""
    if path.suffix.lower() not in (".m4a", ".mp4", ".mp3", ".ogg", ".flac"):
        print(f"[skip] Unsupported extension: {path}", file=sys.stderr)
        return False
    out = path.with_suffix(".wav")
    if out.exists() and not overwrite:
        print(f"[skip] Exists (use --overwrite to replace): {out}", file=sys.stderr)
        return False
    try:
        from pydub import AudioSegment
    except ImportError:
        print("pydub not installed. Run: uv sync (or pip install pydub). ffmpeg must be on PATH for M4A.", file=sys.stderr)
        return False
    try:
        seg = AudioSegment.from_file(str(path))
        seg.export(str(out), format="wav")
        print(f"[ok] {path.name} -> {out.name}")
        return True
    except Exception as e:
        print(f"[fail] {path}: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert M4A (and other formats) to WAV.")
    ap.add_argument("files", nargs="*", type=Path, help="Input .m4a (or other) files.")
    ap.add_argument("--dir", type=Path, help="Convert all .m4a in this directory.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing .wav files.")
    args = ap.parse_args()

    paths: list[Path] = []
    if args.dir:
        if not args.dir.is_dir():
            print(f"Not a directory: {args.dir}", file=sys.stderr)
            return 2
        paths = sorted(args.dir.glob("*.m4a"))
        if not paths:
            print(f"No .m4a files in {args.dir}", file=sys.stderr)
            return 2
    for p in args.files:
        if not p.exists():
            print(f"File not found: {p}", file=sys.stderr)
            return 2
        paths.append(p)

    if not paths:
        ap.print_help()
        return 1

    ok = sum(1 for p in paths if convert_to_wav(p, overwrite=args.overwrite))
    return 0 if ok == len(paths) else 3


if __name__ == "__main__":
    sys.exit(main())
