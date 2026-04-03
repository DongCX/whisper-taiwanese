from __future__ import annotations

import re

from whisper_taiwanese.types import SubtitleCue, TranscriptChunk

SENTENCE_ENDINGS = tuple("。！？!?")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_cues(
    chunks: list[TranscriptChunk],
    max_chars: int = 22,
    max_duration: float = 6.0,
    silence_gap: float = 0.9,
) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    buffer: list[TranscriptChunk] = []

    for chunk in chunks:
        if not buffer:
            buffer.append(chunk)
            continue

        candidate_text = normalize_text("".join(item.text for item in [*buffer, chunk]))
        candidate_duration = chunk.end - buffer[0].start
        gap = max(0.0, chunk.start - buffer[-1].end)
        should_flush = (
            gap >= silence_gap
            or candidate_duration > max_duration
            or len(candidate_text) > max_chars * 2
            or buffer[-1].text.endswith(SENTENCE_ENDINGS)
        )

        if should_flush:
            cues.append(_finalize_buffer(buffer))
            buffer = [chunk]
            continue

        buffer.append(chunk)

    if buffer:
        cues.append(_finalize_buffer(buffer))

    return cues


def _finalize_buffer(buffer: list[TranscriptChunk]) -> SubtitleCue:
    return SubtitleCue(
        start=buffer[0].start,
        end=buffer[-1].end,
        text=normalize_text("".join(item.text for item in buffer)),
    )


def format_timestamp(seconds: float, kind: str) -> str:
    total_millis = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "," if kind == "srt" else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_srt(cues: list[SubtitleCue], max_chars: int = 22, max_lines: int = 2) -> str:
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        lines = wrap_subtitle_text(cue.text, max_chars=max_chars, max_lines=max_lines)
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_timestamp(cue.start, 'srt')} --> {format_timestamp(cue.end, 'srt')}",
                    "\n".join(lines),
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def render_vtt(cues: list[SubtitleCue], max_chars: int = 22, max_lines: int = 2) -> str:
    blocks = ["WEBVTT"]
    for cue in cues:
        lines = wrap_subtitle_text(cue.text, max_chars=max_chars, max_lines=max_lines)
        blocks.append(
            "\n".join(
                [
                    f"{format_timestamp(cue.start, 'vtt')} --> {format_timestamp(cue.end, 'vtt')}",
                    "\n".join(lines),
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def wrap_subtitle_text(text: str, max_chars: int = 22, max_lines: int = 2) -> list[str]:
    normalized = normalize_text(text)
    if len(normalized) <= max_chars:
        return [normalized]

    if " " not in normalized:
        return _wrap_cjk_like(normalized, max_chars=max_chars, max_lines=max_lines)

    words = normalized.split(" ")
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word

    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return lines

    head = lines[: max_lines - 1]
    tail = " ".join(lines[max_lines - 1 :])
    return [*head, tail]


def _wrap_cjk_like(text: str, max_chars: int, max_lines: int) -> list[str]:
    lines = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
    if len(lines) <= max_lines:
        return lines
    head = lines[: max_lines - 1]
    tail = "".join(lines[max_lines - 1 :])
    return [*head, tail]
