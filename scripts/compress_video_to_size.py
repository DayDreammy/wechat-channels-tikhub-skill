#!/usr/bin/env python3
"""Compress a video to target size (MB) using ffmpeg.

Defaults to 50 MB output, keeping audio.
Requires ffmpeg and ffprobe in PATH.
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


def _check_bin(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not found in PATH. Please install ffmpeg/ffprobe.")


def _run(cmd):
    subprocess.run(cmd, check=True)


def _probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    out = subprocess.check_output(cmd)
    data = json.loads(out.decode("utf-8"))
    dur = float(data["format"]["duration"])
    if dur <= 0:
        raise RuntimeError("Invalid duration from ffprobe")
    return dur


def _default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_compressed.mp4")


def _calc_bitrates(target_mb: float, duration_s: float, audio_kbps: int, safety: float) -> int:
    target_bytes = target_mb * 1024 * 1024
    total_bps = (target_bytes * 8) / max(duration_s, 0.001)
    total_bps *= safety
    audio_bps = audio_kbps * 1000
    video_bps = int(total_bps - audio_bps)
    if video_bps <= 0:
        raise RuntimeError("Target size too small for chosen audio bitrate")
    return max(video_bps, 200_000)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress a video to target size using ffmpeg")
    parser.add_argument("--input", required=True, help="Input video path (decrypted MP4)")
    parser.add_argument("--output", help="Output path (default: *_compressed.mp4)")
    parser.add_argument("--target-mb", type=float, default=50.0, help="Target size in MB (default: 50)")
    parser.add_argument("--audio-bitrate", type=int, default=96, help="Audio bitrate in kbps (default: 96)")
    parser.add_argument("--preset", default="medium", help="ffmpeg preset (default: medium)")
    parser.add_argument("--retries", type=int, default=2, help="Extra attempts if file still too large")
    parser.add_argument("--safety", type=float, default=0.96, help="Bitrate safety factor (default: 0.96)")
    args = parser.parse_args()

    _check_bin("ffmpeg")
    _check_bin("ffprobe")

    in_path = Path(args.input)
    if not in_path.exists():
        raise RuntimeError(f"Input not found: {in_path}")

    out_path = Path(args.output) if args.output else _default_output(in_path)

    duration = _probe_duration(in_path)

    safety = args.safety
    for attempt in range(args.retries + 1):
        video_bps = _calc_bitrates(args.target_mb, duration, args.audio_bitrate, safety)
        video_k = int(video_bps / 1000)
        maxrate_k = int(video_k * 1.07)
        bufsize_k = int(video_k * 2)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(in_path),
            "-c:v",
            "libx264",
            "-b:v",
            f"{video_k}k",
            "-maxrate",
            f"{maxrate_k}k",
            "-bufsize",
            f"{bufsize_k}k",
            "-preset",
            args.preset,
            "-c:a",
            "aac",
            "-b:a",
            f"{args.audio_bitrate}k",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        _run(cmd)

        size_mb = out_path.stat().st_size / (1024 * 1024)
        if size_mb <= args.target_mb:
            print(f"OK: {out_path} ({size_mb:.2f} MB)")
            return

        # reduce bitrate and retry
        safety *= 0.9
        print(f"Retry {attempt + 1}: size {size_mb:.2f} MB > {args.target_mb} MB, lowering bitrate")

    raise RuntimeError(f"Failed to reach target size {args.target_mb} MB. Last output: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
