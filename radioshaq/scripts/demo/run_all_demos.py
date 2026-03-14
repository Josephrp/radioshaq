#!/usr/bin/env python3
"""Run all demo scripts in sequence with rich terminal feedback.

Requires the HQ API to be running (e.g. uv run radioshaq run-api).
Optional: --recordings-dir for Option C, from-audio, send-audio, and voice-to-voice demos.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

SCRIPT_DIR = Path(__file__).resolve().parent
# (label, [script_name, ...args with RECORDINGS_DIR/TX_WAV/VOICE_WAV placeholders], short_name)
DEMOS: list[tuple[str, list[str], str]] = [
    ("Inject + relay + poll", ["run_demo.py"], "run_demo"),
    ("Radio RX injection", ["run_radio_rx_injection_demo.py", "--injections", "3", "--store"], "run_radio_rx_injection_demo"),
    ("Callsign register + whitelist", ["run_whitelist_flow_demo.py"], "run_whitelist_flow_demo"),
    ("Orchestrator + Judge", ["run_orchestrator_judge_demo.py"], "run_orchestrator_judge_demo"),
    ("Scheduler", ["run_scheduler_demo.py"], "run_scheduler_demo"),
    ("GIS location + propagation", ["run_gis_demo.py"], "run_gis_demo"),
    ("Voice RX audio (poll)", ["run_voice_rx_audio_demo.py", "--duration", "5"], "run_voice_rx_audio_demo"),
    ("Option C (no Twilio)", ["run_full_live_demo_option_c.py", "--recordings-dir", "RECORDINGS_DIR", "--no-twilio"], "run_full_live_demo_option_c"),
    ("HackRF TX audio", ["run_hackrf_tx_audio_demo.py", "--wav", "TX_WAV"], "run_hackrf_tx_audio_demo"),
    ("Voice-to-voice loop", ["run_voice_to_voice_loop_demo.py", "--wav", "VOICE_WAV"], "run_voice_to_voice_loop_demo"),
]


def run_demo(cmd_args: list[str]) -> tuple[int, str]:
    """Run a demo script; return (exit_code, output). Streams stdout to console in real time."""
    cmd = [sys.executable, "-u"] + cmd_args
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=SCRIPT_DIR.parent.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        out_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            out_lines.append(line)
            console.print(line, end="")
        proc.wait()
        return proc.returncode or 0, "".join(out_lines)
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        return -1, str(e)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run all demos with rich terminal feedback.")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--recordings-dir", type=Path, default=None, help="Path to WAV recordings (enables Option C, TX audio, voice-to-voice)")
    ap.add_argument("--require-hardware", action="store_true", help="Pass --require-hardware to HackRF TX demos")
    ap.add_argument("--skip", nargs="*", default=[], help="Skip demos by short name (e.g. run_full_live_demo_option_c run_hackrf_tx_audio_demo)")
    ap.add_argument("--only", nargs="*", default=[], help="Run only these demos (short names); ignored if empty")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    recordings_dir = args.recordings_dir
    if recordings_dir is not None and not recordings_dir.is_dir():
        console.print(f"[red]Recordings dir not found: {recordings_dir}[/red]")
        return 2

    # Resolve WAV paths for TX demos
    tx_wav: str | None = None
    voice_wav: str | None = None
    if recordings_dir is not None:
        wavs = sorted(recordings_dir.glob("*.wav"))
        if wavs:
            tx_wav = str(wavs[0])
            voice_wav = str(wavs[0])

    console.print(Panel.fit(
        f"[bold]RadioShaq[/bold] – run all demos\n\nBase URL: [cyan]{base}[/cyan]\n"
        + (f"Recordings: [cyan]{recordings_dir}[/cyan]" if recordings_dir else "[dim]No recordings dir (Option C / TX / voice-to-voice skipped)[/dim]"),
        title="All demos",
        border_style="blue",
    ))

    results: list[tuple[str, str, int, float]] = []  # name, status, code, duration
    total_failed = 0
    skip_set = {s.strip().lower() for s in args.skip}
    only_set = {s.strip().lower() for s in args.only} if args.only else None

    for i, (label, script_args, short_name) in enumerate(DEMOS):
        if only_set and short_name.lower() not in only_set:
            continue
        if short_name.lower() in skip_set:
            results.append((label, "skipped", 0, 0.0))
            console.print(f"  [yellow]⊘[/yellow] {label} [dim](skipped)[/dim]")
            continue

        # Substitute placeholders
        final_args = [str(SCRIPT_DIR / script_args[0])]
        for a in script_args[1:]:
            if a == "RECORDINGS_DIR" and recordings_dir is not None:
                final_args.append(str(recordings_dir))
            elif a == "TX_WAV" and tx_wav:
                final_args.append(tx_wav)
            elif a == "VOICE_WAV" and voice_wav:
                final_args.append(voice_wav)
            else:
                final_args.append(a)
        final_args.extend(["--base-url", base])
        if require_hardware := getattr(args, "require_hardware", False):
            if "run_full_live_demo_option_c" in short_name or "run_hackrf_tx_audio_demo" in short_name or "run_voice_to_voice_loop_demo" in short_name:
                final_args.append("--require-hardware")

        # Skip Option C / TX / voice-to-voice if no recordings
        if ("run_full_live_demo_option_c" in short_name or "run_hackrf_tx_audio_demo" in short_name or "run_voice_to_voice_loop_demo" in short_name):
            if recordings_dir is None or (("TX_WAV" in script_args or "VOICE_WAV" in script_args) and not (tx_wav or voice_wav)):
                results.append((label, "skipped", 0, 0.0))
                console.print(f"  [yellow]⊘[/yellow] {label} [dim](no recordings dir or WAV)[/dim]")
                continue

        console.rule(f"[bold blue]{label}[/bold blue]", style="blue")
        t0 = time.perf_counter()
        code, out = run_demo(final_args)
        elapsed = time.perf_counter() - t0

        if code == 0:
            status = "[green]PASS[/green]"
            results.append((label, "pass", 0, elapsed))
        else:
            status = "[red]FAIL[/red]"
            total_failed += 1
            results.append((label, "fail", code, elapsed))

        console.print(f"  [{'green' if code == 0 else 'red'}]{'✓' if code == 0 else '✗'}[/] {label} {status} [dim]({elapsed:.1f}s)[/dim]")

    # Summary table
    table = Table(title="Summary", show_header=True, header_style="bold")
    table.add_column("Demo", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Code", justify="right")
    table.add_column("Time", justify="right")
    for name, st, code, elapsed in results:
        if st == "pass":
            cell = "[green]PASS[/green]"
        elif st == "fail":
            cell = "[red]FAIL[/red]"
        else:
            cell = "[yellow]skipped[/yellow]"
        table.add_row(name, cell, str(code) if code else "—", f"{elapsed:.1f}s" if elapsed else "—")
    console.print()
    console.print(table)
    if total_failed:
        console.print(f"\n[red]{total_failed} demo(s) failed.[/red]")
        return 1
    console.print("\n[green]All run demos passed.[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
