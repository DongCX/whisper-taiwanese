from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TranscriptChunk:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass
class TranscriptResult:
    model: str
    language: str
    device: str
    input_file: Path
    extracted_audio: Path
    text: str
    chunks: list[TranscriptChunk]

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "language": self.language,
            "device": self.device,
            "input_file": str(self.input_file),
            "extracted_audio": str(self.extracted_audio),
            "text": self.text,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }


@dataclass
class SubtitleCue:
    start: float
    end: float
    text: str
