from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import wave

from whisper_taiwanese.subtitles import normalize_text
from whisper_taiwanese.types import TranscriptChunk, TranscriptResult


@dataclass
class RuntimeSpec:
    device_name: str
    torch_dtype: object
    pipeline_device: str


@dataclass
class Transcriber:
    model_id: str
    language: str
    runtime: RuntimeSpec
    backend: str
    inference_object: object
    processor: object | None = None

    def transcribe(self, audio_path: Path, input_path: Path, *, batch_size: int) -> TranscriptResult:
        if self.backend == "pipeline":
            generate_kwargs = _build_generate_kwargs(self.language)
            if self.language != "auto":
                generate_kwargs["language"] = self.language
            result = self.inference_object(
                str(audio_path),
                batch_size=batch_size,
                return_timestamps=True,
                generate_kwargs=generate_kwargs,
            )
            chunks = _normalize_chunks(result.get("chunks", []))
            text = normalize_text(result.get("text", ""))
        else:
            result = _transcribe_with_generate(
                model=self.inference_object,
                processor=self.processor,
                audio_path=audio_path,
                language=self.language,
                device=self.runtime.pipeline_device,
                dtype=self.runtime.torch_dtype,
            )
            chunks = result["chunks"]
            text = result["text"]

        return TranscriptResult(
            model=self.model_id,
            language=self.language,
            device=self.runtime.device_name,
            input_file=input_path.resolve(),
            extracted_audio=audio_path.resolve(),
            text=text,
            chunks=chunks,
        )


def build_transcriber(*, model_id: str, language: str, device: str, chunk_length: float) -> Transcriber:
    runtime = _resolve_runtime(device)

    try:
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    except ImportError as exc:
        raise RuntimeError(
            "Missing runtime dependencies. Run `uv sync --python 3.12` before using the CLI."
        ) from exc

    try:
        if chunk_length > 0:
            pipe = pipeline(
                task="automatic-speech-recognition",
                model=model_id,
                dtype=runtime.torch_dtype,
                device=runtime.pipeline_device,
                chunk_length_s=chunk_length,
            )
            return Transcriber(
                model_id=model_id,
                language=language,
                runtime=runtime,
                backend="pipeline",
                inference_object=pipe,
            )

        processor = AutoProcessor.from_pretrained(model_id)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id, dtype=runtime.torch_dtype)
    except OSError as exc:
        raise RuntimeError(
            "Failed to load the ASR model or tokenizer.\n"
            f"Model: {model_id}\n"
            "If the download was interrupted, check your internet connection and rerun the command.\n"
            "An incomplete Hugging Face cache can also cause this; remove the partial model directory under `~/.cache/huggingface/hub/` and try again."
        ) from exc

    model.to(runtime.pipeline_device)
    return Transcriber(
        model_id=model_id,
        language=language,
        runtime=runtime,
        backend="generate",
        inference_object=model,
        processor=processor,
    )


def _resolve_runtime(device: str) -> RuntimeSpec:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "Missing runtime dependencies. Run `uv sync --python 3.12` before using the CLI."
        ) from exc

    if device == "auto":
        if torch.cuda.is_available():
            return RuntimeSpec("cuda", torch.float16, "cuda:0")
        mps = getattr(torch.backends, "mps", None)
        if mps and mps.is_available():
            return RuntimeSpec("mps", torch.float32, "mps")
        return RuntimeSpec("cpu", torch.float32, "cpu")

    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("`--device cuda` was requested, but CUDA is not available.")
        return RuntimeSpec("cuda", torch.float16, "cuda:0")

    if device == "mps":
        mps = getattr(torch.backends, "mps", None)
        if not mps or not mps.is_available():
            raise RuntimeError("`--device mps` was requested, but MPS is not available.")
        return RuntimeSpec("mps", torch.float32, "mps")

    return RuntimeSpec("cpu", torch.float32, "cpu")


def _normalize_chunks(raw_chunks: list[dict[str, object]]) -> list[TranscriptChunk]:
    chunks: list[TranscriptChunk] = []

    for raw in raw_chunks:
        timestamp = raw.get("timestamp")
        if not isinstance(timestamp, tuple) or len(timestamp) != 2:
            continue

        start_raw, end_raw = timestamp
        if start_raw is None:
            continue

        start = float(start_raw)
        end = float(end_raw) if end_raw is not None else start
        text = normalize_text(str(raw.get("text", "")))
        if not text:
            continue
        chunks.append(TranscriptChunk(start=start, end=max(start, end), text=text))

    if chunks:
        return chunks

    text = normalize_text("".join(str(raw.get("text", "")) for raw in raw_chunks))
    return [TranscriptChunk(start=0.0, end=0.0, text=text)] if text else []


def _transcribe_with_generate(
    *,
    model: object,
    processor: object,
    audio_path: Path,
    language: str,
    device: str,
    dtype: object,
) -> dict[str, object]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "Missing runtime dependencies. Run `uv sync --python 3.12` before using the CLI."
        ) from exc

    audio = _load_pcm16_wave(audio_path)
    inputs = processor(
        audio,
        sampling_rate=16_000,
        return_tensors="pt",
        truncation=False,
        padding="longest",
        return_attention_mask=True,
        do_normalize=True,
    )
    model_inputs = {}
    for key, value in inputs.items():
        if not hasattr(value, "to"):
            model_inputs[key] = value
            continue
        if key == "input_features":
            model_inputs[key] = value.to(device=device, dtype=dtype)
            continue
        model_inputs[key] = value.to(device=device)

    with torch.inference_mode():
        generate_kwargs = _build_generate_kwargs(language)
        try:
            generated = model.generate(**model_inputs, return_segments=True, **generate_kwargs)
        except TypeError:
            generated = model.generate(**model_inputs, **generate_kwargs)

    if hasattr(generated, "get"):
        sequences = generated.get("sequences")
        text = normalize_text(processor.batch_decode(sequences, skip_special_tokens=True)[0])
        segments = generated.get("segments", [[]])[0]
        chunks = _segments_to_chunks(segments, processor)
        return {"text": text, "chunks": chunks}

    text = normalize_text(processor.batch_decode(generated, skip_special_tokens=True)[0])
    return {"text": text, "chunks": [TranscriptChunk(start=0.0, end=0.0, text=text)]}


def _segments_to_chunks(segments: list[dict[str, object]], processor: object) -> list[TranscriptChunk]:
    chunks: list[TranscriptChunk] = []
    for segment in segments:
        tokens = segment.get("tokens")
        if tokens is None:
            continue
        text = normalize_text(processor.decode(tokens, skip_special_tokens=True))
        if not text:
            continue
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        chunks.append(TranscriptChunk(start=start, end=max(start, end), text=text))
    return chunks


def _load_pcm16_wave(audio_path: Path):
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "Missing runtime dependencies. Run `uv sync --python 3.12` before using the CLI."
        ) from exc

    with wave.open(str(audio_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()

        if channels != 1 or sample_width != 2 or sample_rate != 16_000:
            raise RuntimeError(
                f"Expected 16kHz mono PCM16 WAV, got channels={channels}, sample_width={sample_width}, sample_rate={sample_rate}"
            )

        frames = wav_file.readframes(frame_count)

    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32)
    return audio / 32768.0


def _build_generate_kwargs(language: str) -> dict[str, object]:
    generate_kwargs: dict[str, object] = {
        "return_timestamps": True,
        "task": "transcribe",
        "condition_on_prev_tokens": True,
        "temperature": (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        "compression_ratio_threshold": 1.35,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6,
    }
    if language != "auto":
        generate_kwargs["language"] = language
    return generate_kwargs
