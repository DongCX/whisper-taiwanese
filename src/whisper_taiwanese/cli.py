from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from collections.abc import Iterable
from pathlib import Path

from whisper_taiwanese.asr import Transcriber, build_transcriber
from whisper_taiwanese.media import extract_audio
from whisper_taiwanese.models import DEFAULT_PRESET, MODEL_PRESETS
from whisper_taiwanese.subtitles import build_cues, render_srt, render_vtt

SUPPORTED_MEDIA_EXTENSIONS = {
    ".aac",
    ".avi",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}


@dataclass
class TranscriptionJob:
    input_file: Path
    output_dir: Path
    output_stem: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taiwanese-transcribe",
        description="Generate Taiwanese transcript, SRT, VTT, and JSON from a local video/audio file or a directory.",
    )
    parser.add_argument("input", type=Path, help="Path to a local video/audio file or a directory of media files")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for generated transcript and subtitle files",
    )
    parser.add_argument(
        "--output-stem",
        help="Filename stem for generated outputs. Defaults to the input filename stem.",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(MODEL_PRESETS),
        default=DEFAULT_PRESET,
        help="Model preset. Default is `tw-mandarin`; `nutn-v0.5` is tuned for Taiwanese; `balanced` is general Whisper v3 turbo.",
    )
    parser.add_argument(
        "--model",
        help="Override the model preset with any Hugging Face Whisper-compatible model id or local path.",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="Whisper language token. Use `zh` for the NUTN model, or `auto` to let Whisper detect the language.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "mps", "cuda"),
        default="auto",
        help="Execution device. `auto` prefers CUDA, then MPS, then CPU.",
    )
    parser.add_argument(
        "--chunk-length",
        type=float,
        default=0.0,
        help="Optional Whisper pipeline chunk length in seconds. `0` disables chunking and is recommended for accuracy.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for the Hugging Face ASR pipeline.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=22,
        help="Preferred maximum characters per subtitle line.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=6.0,
        help="Preferred maximum seconds per subtitle cue when merging segments.",
    )
    parser.add_argument(
        "--keep-wav",
        action="store_true",
        help="Keep the extracted 16k mono WAV next to the output files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        parser.error(f"Input file does not exist: {input_path}")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    model_id = args.model or MODEL_PRESETS[args.preset]

    jobs = build_jobs(input_path, output_dir, output_stem=args.output_stem)
    planned_outputs = collect_output_paths(jobs, keep_wav=args.keep_wav)
    _ensure_writable(planned_outputs, overwrite=args.overwrite)

    if len(jobs) > 1:
        print(f"Found {len(jobs)} media files under {input_path}", file=sys.stderr)
    print(f"Loading model: {model_id}", file=sys.stderr)
    transcriber = build_transcriber(
        model_id=model_id,
        language=args.language,
        device=args.device,
        chunk_length=args.chunk_length,
    )

    for index, job in enumerate(jobs, start=1):
        process_job(
            job,
            transcriber=transcriber,
            batch_size=args.batch_size,
            max_chars=args.max_chars,
            max_seconds=args.max_seconds,
            keep_wav=args.keep_wav,
            index=index,
            total=len(jobs),
        )

    if len(jobs) > 1:
        print(f"Completed {len(jobs)} files", file=sys.stderr)

    return 0


def build_jobs(input_path: Path, output_dir: Path, *, output_stem: str | None) -> list[TranscriptionJob]:
    if input_path.is_file():
        return [
            TranscriptionJob(
                input_file=input_path,
                output_dir=output_dir,
                output_stem=output_stem or input_path.stem,
            )
        ]

    if output_stem:
        raise SystemExit("`--output-stem` can only be used with a single input file.")

    media_files = discover_media_files(input_path, exclude_dirs=[output_dir])
    if not media_files:
        raise SystemExit(
            f"No supported media files were found under {input_path}. "
            f"Supported extensions: {', '.join(sorted(SUPPORTED_MEDIA_EXTENSIONS))}"
        )

    jobs: list[TranscriptionJob] = []
    used_roots: set[Path] = set()
    for media_file in media_files:
        relative_parent = media_file.relative_to(input_path).parent
        job_output_dir = output_dir / relative_parent
        job_stem = _build_unique_stem(media_file, job_output_dir, used_roots)
        jobs.append(
            TranscriptionJob(
                input_file=media_file,
                output_dir=job_output_dir,
                output_stem=job_stem,
            )
        )
    return jobs


def discover_media_files(input_dir: Path, exclude_dirs: Iterable[Path] = ()) -> list[Path]:
    excluded = [path.resolve() for path in exclude_dirs if _is_relative_to(path.resolve(), input_dir.resolve())]
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS
        and not any(_is_relative_to(path, excluded_dir) for excluded_dir in excluded)
    )


def collect_output_paths(jobs: Iterable[TranscriptionJob], *, keep_wav: bool) -> list[Path]:
    paths: list[Path] = []
    for job in jobs:
        outputs = _build_output_paths(job.output_dir, job.output_stem)
        paths.extend(outputs.values())
        if keep_wav:
            paths.append(job.output_dir / f"{job.output_stem}.wav")
    return paths


def process_job(
    job: TranscriptionJob,
    *,
    transcriber: Transcriber,
    batch_size: int,
    max_chars: int,
    max_seconds: float,
    keep_wav: bool,
    index: int,
    total: int,
) -> None:
    job.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = _build_output_paths(job.output_dir, job.output_stem)

    print(f"[{index}/{total}] extracting audio from {job.input_file}", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix="whisper-taiwanese-") as temp_dir:
        extracted_audio = Path(temp_dir) / f"{job.output_stem}.wav"
        extract_audio(job.input_file, extracted_audio)

        print(f"[{index}/{total}] transcribing {job.input_file.name}", file=sys.stderr)
        transcript = transcriber.transcribe(
            extracted_audio,
            job.input_file,
            batch_size=batch_size,
        )

        if keep_wav:
            wav_path = job.output_dir / f"{job.output_stem}.wav"
            wav_path.write_bytes(extracted_audio.read_bytes())
            print(str(wav_path))

    print(f"[{index}/{total}] writing outputs", file=sys.stderr)
    cues = build_cues(
        transcript.chunks,
        max_chars=max_chars,
        max_duration=max_seconds,
    )

    outputs["txt"].write_text(transcript.text + "\n", encoding="utf-8")
    outputs["json"].write_text(
        json.dumps(
            {
                **transcript.to_dict(),
                "subtitle_cues": [
                    {"start": cue.start, "end": cue.end, "text": cue.text} for cue in cues
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["srt"].write_text(render_srt(cues, max_chars=max_chars), encoding="utf-8")
    outputs["vtt"].write_text(render_vtt(cues, max_chars=max_chars), encoding="utf-8")

    for path in outputs.values():
        print(str(path))


def _build_output_paths(output_dir: Path, output_stem: str) -> dict[str, Path]:
    return {
        "txt": output_dir / f"{output_stem}.txt",
        "json": output_dir / f"{output_stem}.json",
        "srt": output_dir / f"{output_stem}.srt",
        "vtt": output_dir / f"{output_stem}.vtt",
    }


def _build_unique_stem(input_file: Path, output_dir: Path, used_roots: set[Path]) -> str:
    suffix_label = input_file.suffix.lower().lstrip(".") or "media"
    candidates = [input_file.stem, f"{input_file.stem}_{suffix_label}"]

    for candidate in candidates:
        root = output_dir / candidate
        if root not in used_roots:
            used_roots.add(root)
            return candidate

    index = 2
    while True:
        candidate = f"{input_file.stem}_{suffix_label}_{index}"
        root = output_dir / candidate
        if root not in used_roots:
            used_roots.add(root)
            return candidate
        index += 1


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _ensure_writable(paths: Iterable[Path], *, overwrite: bool) -> None:
    for path in paths:
        if path.exists() and not overwrite:
            raise SystemExit(f"Refusing to overwrite existing file: {path}. Pass --overwrite to replace it.")
