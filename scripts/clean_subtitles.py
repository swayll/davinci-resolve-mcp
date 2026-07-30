#!/usr/bin/env python3
"""Clean and reformat SRT subtitles.

Processing order per entry:
  1. First pass: strip HTML tags, remove punctuation at start/end of line
  2. Split long lines (> N words) into proportional-timed sub-entries,
     with punctuation removal on each chunk
  3. Second punctuation pass on every sub-entry (cleans up split artifacts)
  4. Move hanging prepositions / conjunctions / particles / pronouns
     from end of sub-entry to start of the next
  5. Quote characters («»\"') are preserved at line boundaries

Usage:
    python scripts/clean_subtitles.py input.srt [--max-words 4] [--output out.srt]
    python scripts/clean_subtitles.py input.srt [--max-words 4]   # writes input_clean.srt
"""

import argparse
import math
import os
import re
import sys

STOP_WORDS = {
    "в",
    "без",
    "до",
    "для",
    "за",
    "из",
    "к",
    "на",
    "над",
    "о",
    "об",
    "от",
    "по",
    "под",
    "при",
    "про",
    "с",
    "у",
    "через",
    "и",
    "а",
    "но",
    "да",
    "или",
    "же",
    "ли",
    "бы",
    "не",
    "ни",
    "ну",
    "ведь",
    "вот",
    "даже",
    "разве",
    "уж",
    "ещё",
    "еще",
    "лишь",
    "со",
    "во",
    "ко",
    "обо",
    "надо",
    "подо",
    "перед",
    "пред",
    "изо",
    "я",
    "мы",
    "ты",
    "вы",
    "он",
    "она",
    "оно",
    "они",
    "меня",
    "нас",
    "тебя",
    "вас",
    "его",
    "её",
    "ее",
    "их",
    "мне",
    "нам",
    "тебе",
    "вам",
    "ему",
    "ей",
    "им",
    "мной",
    "мною",
    "нами",
    "тобой",
    "тобою",
    "вами",
    "ними",
    "нём",
    "нем",
    "ней",
    "них",
    "мой",
    "моя",
    "моё",
    "мое",
    "мои",
    "моей",
    "моих",
    "твой",
    "твоя",
    "твоё",
    "твое",
    "твои",
    "наш",
    "наша",
    "наше",
    "наши",
    "ваш",
    "ваша",
    "ваше",
    "ваши",
    "свой",
    "своя",
    "своё",
    "свое",
    "свои",
    "себя",
    "себе",
    "собой",
}

HTML_TAG = re.compile(r"<[^>]+>")

LEAD_PUNCT = re.compile(r"^[.,;:\u2014\u2013()\[\]{}—–…]+")
TAIL_PUNCT = re.compile(r"[.,;:\u2014\u2013()\[\]{}—–…]+$")

SRT_BLOCK = re.compile(
    r"(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n"
    r"((?:.+\n?)*?)(?=\n\s*\n|\Z)",
    re.MULTILINE,
)


def time_to_ms(t_str):
    t_str = t_str.replace(",", ".")
    h, m, rest = t_str.split(":")
    s, ms = rest.split(".")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def ms_to_time(ms):
    total = max(0, int(round(ms)))
    h = total // 3600000
    total %= 3600000
    m = total // 60000
    total %= 60000
    s = total // 1000
    frac = total % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{frac:03d}"


def clean_punctuation(text):
    text = HTML_TAG.sub("", text)
    text = LEAD_PUNCT.sub("", text)
    text = TAIL_PUNCT.sub("", text)
    return text.strip()


def strip_word_punctuation(word):
    return word.strip(".,!?;:—–«»\"'()[]{}…")


def find_hanging_index(words):
    if not words:
        return None
    last_raw = words[-1]
    last_clean = strip_word_punctuation(last_raw)
    if last_clean.lower() in STOP_WORDS:
        return len(words) - 1
    return None


def distribute_words(words, num_parts):
    base = len(words) // num_parts
    rem = len(words) % num_parts
    parts = []
    idx = 0
    for i in range(num_parts):
        size = base + (1 if i < rem else 0)
        parts.append(words[idx : idx + size])
        idx += size
    return parts


def parse_srt(text):
    entries = []
    for match in SRT_BLOCK.finditer(text):
        idx_str, start_str, end_str, raw_text = match.groups()
        lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
        text_joined = " ".join(lines)
        entries.append(
            {
                "index": int(idx_str),
                "start": start_str,
                "end": end_str,
                "start_ms": time_to_ms(start_str),
                "end_ms": time_to_ms(end_str),
                "text": text_joined,
            }
        )
    return entries


def format_srt(entries, start_index=1):
    lines = []
    for i, e in enumerate(entries):
        lines.append(str(start_index + i))
        lines.append(f"{e['start']} --> {e['end']}")
        lines.append(e["text"])
        lines.append("")
    return "\n".join(lines)


def process_entries(entries, max_words):
    result = []
    hang_buffer = None

    for entry in entries:
        text = entry["text"].replace("\n", " ")
        text = clean_punctuation(text)

        if hang_buffer:
            text = hang_buffer + " " + text if text else hang_buffer
            hang_buffer = None

        text = text.strip()
        if not text:
            continue

        words = text.split()
        if len(words) <= max_words:
            sub_entries = [
                {
                    "start_ms": entry["start_ms"],
                    "end_ms": entry["end_ms"],
                    "start": entry["start"],
                    "end": entry["end"],
                    "text": text,
                }
            ]
        else:
            num_parts = math.ceil(len(words) / max_words)
            chunks = distribute_words(words, num_parts)
            total_words = len(words)
            total_ms = entry["end_ms"] - entry["start_ms"]
            sub_entries = []
            cumulative = 0
            for chunk in chunks:
                chunk_len = len(chunk)
                chunk_start = entry["start_ms"] + int(
                    total_ms * cumulative / total_words
                )
                cumulative += chunk_len
                chunk_end = entry["start_ms"] + int(total_ms * cumulative / total_words)
                chunk_text = clean_punctuation(" ".join(chunk))
                if chunk_text:
                    sub_entries.append(
                        {
                            "start_ms": chunk_start,
                            "end_ms": chunk_end,
                            "text": chunk_text,
                        }
                    )

        # Second punctuation pass before hang-word detection
        for se in sub_entries:
            se["text"] = clean_punctuation(se["text"])

        # Apply hang-word check across sub_entries
        for i in range(len(sub_entries)):
            se = sub_entries[i]
            se_words = se["text"].split()
            hang_idx = find_hanging_index(se_words)

            if hang_idx is not None and i < len(sub_entries) - 1:
                hang_word = strip_word_punctuation(se_words[hang_idx])
                se_words.pop(hang_idx)
                se["text"] = " ".join(se_words).strip() if se_words else ""
                sub_entries[i + 1]["text"] = (
                    hang_word + " " + sub_entries[i + 1]["text"]
                )
            elif hang_idx is not None and i == len(sub_entries) - 1:
                hang_word = strip_word_punctuation(se_words[hang_idx])
                se_words.pop(hang_idx)
                se["text"] = " ".join(se_words).strip() if se_words else ""
                hang_buffer = hang_word

        # Collect non-empty entries
        for se in sub_entries:
            se["text"] = clean_punctuation(se["text"])
            if se["text"]:
                se["start"] = ms_to_time(se["start_ms"])
                se["end"] = ms_to_time(se["end_ms"])
                result.append(se)

    return result, hang_buffer


def main():
    parser = argparse.ArgumentParser(description="Clean and reformat SRT subtitles")
    parser.add_argument("input", help="Path to input SRT file")
    parser.add_argument(
        "--max-words",
        type=int,
        default=4,
        help="Maximum words per subtitle (default: 4)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output path (default: input file with _clean suffix)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"Error: input file not found: {args.input}")

    with open(args.input, "r", encoding="utf-8-sig") as f:
        raw = f.read()

    entries = parse_srt(raw)
    if not entries:
        sys.exit("Error: no SRT entries found in input file")

    processed, _ = process_entries(entries, args.max_words)

    output_text = format_srt(processed)

    if not args.output:
        base, ext = os.path.splitext(args.input)
        args.output = f"{base}_clean{ext}"

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output_text)


if __name__ == "__main__":
    main()
