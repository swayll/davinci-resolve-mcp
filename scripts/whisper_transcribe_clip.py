#!/usr/bin/env python3
"""Transcribe the current timeline's V2 clip using whisper-cli + ffmpeg.

Extracts the fragment's audio from the source file using provided time bounds,
runs whisper-cli, then post-processes with clean_subtitles.py.

Usage:
    python scripts/whisper_transcribe_clip.py \
        --start-time "00:12:19.884" \
        --end-time "00:12:50.489" \
        [--model ~/.cache/whisper/models/ggml-medium.bin] \
        [--output-dir <dir>] \
        [--max-words 4]
"""

import argparse
import os
import subprocess
import sys
import tempfile

import DaVinciResolveScript as dvr_script

DEFAULT_MODEL = os.path.expanduser("~/.cache/whisper/models/ggml-medium.bin")
DEFAULT_MAX_WORDS = 4


def resolve_source_path():
    resolve = dvr_script.scriptapp("Resolve")
    if not resolve:
        sys.exit("Error: Cannot connect to DaVinci Resolve. Is it running?")

    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        sys.exit("Error: No current project open")

    timeline = proj.GetCurrentTimeline()
    if not timeline:
        sys.exit("Error: No current timeline")

    items = timeline.GetItemsInTrack("video", 2)
    if not items:
        sys.exit("Error: No items on video track 2. Place the clip first.")

    keys = sorted(items.keys())
    item = items[keys[0]]
    mp_item = item.GetMediaPoolItem()
    if not mp_item:
        sys.exit("Error: No MediaPoolItem for clip on V2")

    path = mp_item.GetClipProperty("File Path")
    if not path:
        path = mp_item.GetClipProperty("File Name")
    if not path:
        sys.exit("Error: Could not get source file path from the clip")
    return path


def extract_audio_fragment(source_path, start_time, end_time, work_dir):
    wav_path = os.path.join(work_dir, "fragment_audio.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-ss", start_time,
        "-to", end_time,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-sample_fmt", "s16",
        wav_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return wav_path


def run_whisper(wav_path, model_path, work_dir):
    base = os.path.join(work_dir, "transcript_raw")
    cmd = [
        "whisper-cli",
        "-f", wav_path,
        "-m", model_path,
        "-l", "ru",
        "--print-colors",
        "--output-srt",
        "-of", base,
    ]
    subprocess.run(cmd, check=True)
    raw_srt = base + ".srt"
    if not os.path.exists(raw_srt):
        sys.exit(f"Error: whisper-cli did not produce expected output at {raw_srt}")
    return raw_srt


def clean_subtitles(raw_srt, max_words, work_dir):
    clean_path = os.path.join(work_dir, "transcript_clean.srt")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cleaner = os.path.join(script_dir, "clean_subtitles.py")
    subprocess.run(
        [
            sys.executable,
            cleaner,
            raw_srt,
            "--max-words", str(max_words),
            "--output", clean_path,
        ],
        check=True,
    )
    return clean_path


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe the current timeline's V2 clip via whisper-cli"
    )
    parser.add_argument(
        "--start-time", required=True,
        help="Fragment start time, e.g. '00:12:19.884'",
    )
    parser.add_argument(
        "--end-time", required=True,
        help="Fragment end time, e.g. '00:12:50.489'",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help="Path to whisper model file (default: ggml-medium.bin)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Output directory (default: temp dir)",
    )
    parser.add_argument(
        "--max-words", type=int, default=DEFAULT_MAX_WORDS,
        help=f"Max words per subtitle (default: {DEFAULT_MAX_WORDS})",
    )
    args = parser.parse_args()

    source_path = resolve_source_path()
    print(f"Source: {source_path}")

    work_dir = args.output_dir or tempfile.mkdtemp(prefix="whisper_")
    os.makedirs(work_dir, exist_ok=True)

    print("Extracting audio fragment via ffmpeg...")
    wav_path = extract_audio_fragment(
        source_path, args.start_time, args.end_time, work_dir
    )
    print(f"WAV: {wav_path}")

    print("Running whisper-cli...")
    raw_srt = run_whisper(wav_path, args.model, work_dir)
    print(f"Raw SRT: {raw_srt}")

    print("Post-processing subtitles...")
    clean_path = clean_subtitles(raw_srt, args.max_words, work_dir)
    print(f"Clean SRT: {clean_path}")

    print(f"\nDone! Import into DaVinci Resolve:")
    print(f"  File > Import > Subtitle > \"{clean_path}\"")
    print(f"  Then confirm completion to continue.")


if __name__ == "__main__":
    main()
