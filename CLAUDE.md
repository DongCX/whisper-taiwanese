# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make sync          # Install dependencies (uv sync --python 3.12)
make test          # Run unit tests
make transcribe INPUT=/path/to/video.mp4   # Transcribe a single file
make batch INPUT=/path/to/folder           # Batch transcribe a directory
```

Running tests directly:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Optional Makefile variables: `OUT=`, `STEM=`, `PRESET=tw-mandarin|nutn-v0.5|balanced`, `DEVICE=auto|cpu|mps|cuda`, `FLAGS=`.

## Architecture

This is a local CLI for Taiwanese speech recognition (ASR) and subtitle generation. The entry point is `taiwanese-transcribe` → `whisper_taiwanese.cli:main()`.

**Data flow:**
1. `cli.py` — parses args, builds jobs (single file or batch directory), calls `process_job()` per file
2. `media.py` — extracts 16kHz mono WAV via ffmpeg
3. `asr.py` — runs HuggingFace ASR pipeline, returns `TranscriptResult` with `TranscriptChunk` list
4. `subtitles.py` — merges chunks into `SubtitleCue` list based on silence gaps, duration, and char limits
5. `cli.py` — writes `.txt`, `.json`, `.srt`, `.vtt` (and optionally `.wav`)

**Key modules:**
- `types.py` — `TranscriptChunk`, `TranscriptResult`, `SubtitleCue` dataclasses
- `models.py` — `MODEL_PRESETS` dict (three presets: `tw-mandarin` default, `nutn-v0.5`, `balanced`)
- `asr.py` — `Transcriber` dataclass with two backends: `pipeline` (HuggingFace chunked pipeline) and `generate` (direct inference)

**Device selection:** Auto-detects CUDA → MPS → CPU; uses float16 for CUDA, float32 otherwise.

**Batch collision avoidance:** When multiple files in the same directory share a stem but differ by extension, a suffix is appended to output filenames.
