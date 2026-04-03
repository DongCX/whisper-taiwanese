from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg"):
        return
    raise RuntimeError("`ffmpeg` was not found in PATH. Install ffmpeg before running this tool.")


def extract_audio(input_path: Path, output_path: Path, sample_rate: int = 16_000) -> Path:
    ensure_ffmpeg_available()
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "ffmpeg failed while extracting audio.\n"
            f"Command: {' '.join(command)}\n"
            f"stderr:\n{completed.stderr.strip()}"
        )
    return output_path
