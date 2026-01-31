#!/usr/bin/env python3
"""Extract audio from a video using ffmpeg."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _check_bin(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not found in PATH. Please install ffmpeg.")


def _default_output(input_path: Path, codec: str) -> Path:
    ext = {"aac": "m4a", "mp3": "mp3", "flac": "flac", "opus": "opus"}.get(codec, "m4a")
    return input_path.with_suffix(f".{ext}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract audio from a video using ffmpeg")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", help="Output audio path (default based on codec)")
    parser.add_argument("--codec", default="aac", help="Audio codec (default: aac)")
    parser.add_argument("--bitrate", type=int, default=128, help="Audio bitrate kbps (default: 128)")
    args = parser.parse_args()

    _check_bin("ffmpeg")

    in_path = Path(args.input)
    if not in_path.exists():
        raise RuntimeError(f"Input not found: {in_path}")

    out_path = Path(args.output) if args.output else _default_output(in_path, args.codec)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(in_path),
        "-vn",
        "-c:a",
        args.codec,
        "-b:a",
        f"{args.bitrate}k",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    print(f"OK: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
